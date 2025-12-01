/*
 * PTY-based STP Bluetooth Bridge with Line Discipline Attachment
 *
 * Creates a pseudo-terminal, bridges /dev/stpbt data through it,
 * and directly attaches the HCI UART line discipline (N_HCI).
 *
 * This version doesn't require ldattach - it uses ioctl(TIOCSETD).
 *
 * Author: Lucas Zampieri <lzampier@redhat.com>
 * Date: December 1, 2025
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <termios.h>

#define STPBT_DEVICE "/dev/stpbt"
#define PTY_SYMLINK "/tmp/bt_pty"
#define BUFFER_SIZE 4096

/* Line discipline numbers from kernel headers */
#define N_TTY       0   /* Default TTY line discipline */
#define N_HCI       15  /* Bluetooth HCI UART line discipline */

/* For TIOCSETD (set line discipline) */
#ifndef TIOCSETD
#define TIOCSETD    0x5423
#endif

static volatile int running = 1;

void signal_handler(int signum) {
    (void)signum;
    running = 0;
}

void setup_signal_handlers(void) {
    struct sigaction sa = {0};
    sa.sa_handler = signal_handler;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}

int open_stpbt(void) {
    int fd, flags;

    /* Open in blocking mode first */
    fd = open(STPBT_DEVICE, O_RDWR | O_NOCTTY);
    if (fd < 0) {
        perror("Failed to open " STPBT_DEVICE);
        return -1;
    }

    /* Now make it non-blocking */
    flags = fcntl(fd, F_GETFL, 0);
    if (flags >= 0) {
        fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    }

    printf("Opened %s (fd=%d)\n", STPBT_DEVICE, fd);
    return fd;
}

int create_pty(char **slave_name) {
    int master_fd;
    char *slave;

    /* Create PTY master */
    master_fd = posix_openpt(O_RDWR | O_NOCTTY);
    if (master_fd < 0) {
        perror("posix_openpt failed");
        return -1;
    }

    /* Grant access and unlock */
    if (grantpt(master_fd) < 0) {
        perror("grantpt failed");
        close(master_fd);
        return -1;
    }

    if (unlockpt(master_fd) < 0) {
        perror("unlockpt failed");
        close(master_fd);
        return -1;
    }

    /* Get slave name */
    slave = ptsname(master_fd);
    if (!slave) {
        perror("ptsname failed");
        close(master_fd);
        return -1;
    }

    *slave_name = strdup(slave);

    printf("Created PTY master (fd=%d)\n", master_fd);
    printf("PTY slave: %s\n", *slave_name);

    /* Create symlink for convenience */
    unlink(PTY_SYMLINK);
    if (symlink(*slave_name, PTY_SYMLINK) == 0) {
        printf("Created symlink: %s -> %s\n", PTY_SYMLINK, *slave_name);
    }

    return master_fd;
}

int attach_line_discipline(const char *slave_name) {
    int slave_fd;
    int ldisc;

    /* Open PTY slave */
    slave_fd = open(slave_name, O_RDWR | O_NOCTTY);
    if (slave_fd < 0) {
        perror("Failed to open PTY slave");
        return -1;
    }

    printf("\nAttaching line discipline...\n");
    printf("Opening PTY slave: %s (fd=%d)\n", slave_name, slave_fd);

    /* Set line discipline to N_HCI */
    ldisc = N_HCI;
    if (ioctl(slave_fd, TIOCSETD, &ldisc) < 0) {
        perror("Failed to set HCI line discipline (TIOCSETD)");
        printf("Error: %s\n", strerror(errno));
        printf("\nThis may mean:\n");
        printf("  1. hci_uart module not loaded: modprobe hci_uart\n");
        printf("  2. Kernel doesn't support N_HCI line discipline\n");
        printf("  3. Insufficient permissions\n");
        close(slave_fd);
        return -1;
    }

    printf("Successfully attached N_HCI line discipline (15)\n");

    /* Keep slave_fd open - closing it would detach the line discipline */
    return slave_fd;
}

ssize_t safe_read(int fd, void *buf, size_t count) {
    ssize_t n;
    do {
        n = read(fd, buf, count);
    } while (n < 0 && errno == EINTR);
    return n;
}

ssize_t safe_write(int fd, const void *buf, size_t count) {
    size_t total = 0;
    while (total < count) {
        ssize_t n = write(fd, (const char *)buf + total, count - total);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        total += n;
    }
    return total;
}

void bridge_data(int stpbt_fd, int pty_master_fd) {
    struct pollfd fds[2];
    unsigned char buffer[BUFFER_SIZE];
    ssize_t n;

    fds[0].fd = stpbt_fd;
    fds[0].events = POLLIN;
    fds[1].fd = pty_master_fd;
    fds[1].events = POLLIN;

    printf("\nBridge active. Data flow:\n");
    printf("  /dev/stpbt <-> PTY master <-> PTY slave <-> hci_uart <-> hci0\n");
    printf("\nPress Ctrl+C to stop.\n\n");

    while (running) {
        int ret = poll(fds, 2, 1000);

        if (ret < 0) {
            if (errno == EINTR)
                continue;
            perror("poll failed");
            break;
        }

        if (ret == 0)
            continue;

        /* stpbt -> pty */
        if (fds[0].revents & POLLIN) {
            n = safe_read(stpbt_fd, buffer, sizeof(buffer));
            if (n < 0) {
                if (errno != EAGAIN && errno != EWOULDBLOCK) {
                    perror("Read from stpbt failed");
                    break;
                }
            } else if (n > 0) {
                printf("stpbt -> pty: %zd bytes\n", n);
                if (safe_write(pty_master_fd, buffer, n) < 0) {
                    perror("Write to pty failed");
                    break;
                }
            }
        }

        /* pty -> stpbt */
        if (fds[1].revents & POLLIN) {
            n = safe_read(pty_master_fd, buffer, sizeof(buffer));
            if (n < 0) {
                if (errno != EAGAIN && errno != EWOULDBLOCK) {
                    perror("Read from pty failed");
                    break;
                }
            } else if (n > 0) {
                printf("pty -> stpbt: %zd bytes\n", n);
                if (safe_write(stpbt_fd, buffer, n) < 0) {
                    perror("Write to stpbt failed");
                    break;
                }
            }
        }

        /* Check for errors */
        if ((fds[0].revents & (POLLERR | POLLHUP | POLLNVAL)) ||
            (fds[1].revents & (POLLERR | POLLHUP | POLLNVAL))) {
            fprintf(stderr, "Poll error detected\n");
            break;
        }
    }
}

int main(void) {
    int stpbt_fd = -1;
    int pty_master_fd = -1;
    int pty_slave_fd = -1;
    char *slave_name = NULL;

    printf("PTY-based STP Bluetooth Bridge (with line discipline)\n");
    printf("======================================================\n\n");
    fflush(stdout);

    setup_signal_handlers();

    /* Open stpbt device */
    printf("[DEBUG] Opening stpbt device...\n");
    fflush(stdout);
    stpbt_fd = open_stpbt();
    if (stpbt_fd < 0) {
        printf("[ERROR] Failed to open stpbt\n");
        fflush(stdout);
        return EXIT_FAILURE;
    }
    printf("[DEBUG] stpbt opened successfully (fd=%d)\n", stpbt_fd);
    fflush(stdout);

    /* Create PTY */
    printf("[DEBUG] Creating PTY...\n");
    fflush(stdout);
    pty_master_fd = create_pty(&slave_name);
    if (pty_master_fd < 0) {
        printf("[ERROR] Failed to create PTY\n");
        fflush(stdout);
        close(stpbt_fd);
        return EXIT_FAILURE;
    }
    printf("[DEBUG] PTY created successfully (master_fd=%d, slave=%s)\n", pty_master_fd, slave_name);
    fflush(stdout);

    /* Attach HCI line discipline to PTY slave */
    printf("[DEBUG] Attaching line discipline...\n");
    fflush(stdout);
    pty_slave_fd = attach_line_discipline(slave_name);
    if (pty_slave_fd < 0) {
        printf("[ERROR] Failed to attach line discipline\n");
        fflush(stdout);
        close(pty_master_fd);
        close(stpbt_fd);
        free(slave_name);
        return EXIT_FAILURE;
    }
    printf("[DEBUG] Line discipline attached successfully (slave_fd=%d)\n", pty_slave_fd);
    fflush(stdout);

    printf("\nWaiting for hci0 to appear (may take a few seconds)...\n");
    fflush(stdout);
    sleep(2);

    /* Bridge data between stpbt and pty master */
    printf("[DEBUG] Starting bridge...\n");
    fflush(stdout);
    bridge_data(stpbt_fd, pty_master_fd);

    /* Cleanup */
    printf("\nShutting down...\n");

    /* Reset line discipline before closing */
    int ldisc = N_TTY;
    ioctl(pty_slave_fd, TIOCSETD, &ldisc);

    close(pty_slave_fd);
    close(pty_master_fd);
    close(stpbt_fd);
    unlink(PTY_SYMLINK);
    free(slave_name);

    return EXIT_SUCCESS;
}
