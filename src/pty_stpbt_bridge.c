/*
 * PTY-based STP Bluetooth Bridge
 *
 * Creates a pseudo-terminal and bridges /dev/stpbt data through it,
 * allowing the hci_uart driver to be attached via ldattach.
 *
 * Usage:
 *   ./pty_stpbt_bridge
 *   # In another terminal:
 *   ldattach -d -s 115200 15 /tmp/bt_pty
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

#define STPBT_DEVICE "/dev/stpbt"
#define PTY_SYMLINK "/tmp/bt_pty"
#define BUFFER_SIZE 4096

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
    int fd = open(STPBT_DEVICE, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        perror("Failed to open " STPBT_DEVICE);
        return -1;
    }

    printf("Opened %s (fd=%d)\n", STPBT_DEVICE, fd);
    return fd;
}

int create_pty(char **slave_name) {
    int master_fd;
    char *slave;

    // Create PTY master
    master_fd = posix_openpt(O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (master_fd < 0) {
        perror("posix_openpt failed");
        return -1;
    }

    // Grant access and unlock
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

    // Get slave name
    slave = ptsname(master_fd);
    if (!slave) {
        perror("ptsname failed");
        close(master_fd);
        return -1;
    }

    *slave_name = strdup(slave);

    printf("Created PTY master (fd=%d)\n", master_fd);
    printf("PTY slave: %s\n", *slave_name);

    // Create symlink for convenience
    unlink(PTY_SYMLINK);
    if (symlink(*slave_name, PTY_SYMLINK) == 0) {
        printf("Created symlink: %s -> %s\n", PTY_SYMLINK, *slave_name);
    }

    return master_fd;
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

void bridge_data(int stpbt_fd, int pty_fd) {
    struct pollfd fds[2];
    unsigned char buffer[BUFFER_SIZE];
    ssize_t n;

    fds[0].fd = stpbt_fd;
    fds[0].events = POLLIN;
    fds[1].fd = pty_fd;
    fds[1].events = POLLIN;

    printf("\nBridge active. Waiting for data...\n");
    printf("Press Ctrl+C to stop.\n\n");

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

        // stpbt -> pty
        if (fds[0].revents & POLLIN) {
            n = safe_read(stpbt_fd, buffer, sizeof(buffer));
            if (n < 0) {
                if (errno != EAGAIN && errno != EWOULDBLOCK) {
                    perror("Read from stpbt failed");
                    break;
                }
            } else if (n > 0) {
                printf("stpbt -> pty: %zd bytes\n", n);
                if (safe_write(pty_fd, buffer, n) < 0) {
                    perror("Write to pty failed");
                    break;
                }
            }
        }

        // pty -> stpbt
        if (fds[1].revents & POLLIN) {
            n = safe_read(pty_fd, buffer, sizeof(buffer));
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

        // Check for errors
        if ((fds[0].revents & (POLLERR | POLLHUP | POLLNVAL)) ||
            (fds[1].revents & (POLLERR | POLLHUP | POLLNVAL))) {
            fprintf(stderr, "Poll error detected\n");
            break;
        }
    }
}

int main(void) {
    int stpbt_fd = -1;
    int pty_fd = -1;
    char *slave_name = NULL;

    printf("PTY-based STP Bluetooth Bridge\n");
    printf("================================\n\n");

    setup_signal_handlers();

    // Open stpbt device
    stpbt_fd = open_stpbt();
    if (stpbt_fd < 0) {
        return EXIT_FAILURE;
    }

    // Create PTY
    pty_fd = create_pty(&slave_name);
    if (pty_fd < 0) {
        close(stpbt_fd);
        return EXIT_FAILURE;
    }

    printf("\nTo attach hci_uart line discipline, run:\n");
    printf("  ldattach -d -s 115200 15 %s\n", PTY_SYMLINK);
    printf("or:\n");
    printf("  ldattach -d -s 115200 15 %s\n\n", slave_name);

    // Bridge data
    bridge_data(stpbt_fd, pty_fd);

    // Cleanup
    printf("\nShutting down...\n");
    close(stpbt_fd);
    close(pty_fd);
    unlink(PTY_SYMLINK);
    free(slave_name);

    return EXIT_SUCCESS;
}
