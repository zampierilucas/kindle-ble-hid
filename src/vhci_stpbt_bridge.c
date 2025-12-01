/*
 * VHCI to stpbt bridge for MediaTek BT on Kindle
 *
 * This program bridges the Linux Virtual HCI interface (/dev/vhci)
 * to the MediaTek STP Bluetooth character device (/dev/stpbt).
 *
 * When run, it:
 * 1. Opens /dev/vhci - this creates a virtual HCI device (hci0)
 * 2. Opens /dev/stpbt - the MediaTek BT data channel
 * 3. Proxies HCI packets between them (both directions)
 *
 * The /dev/stpbt device uses H4 protocol (packet type + HCI packet),
 * which is exactly what /dev/vhci expects.
 *
 * Build for Kindle (ARMv7):
 *   arm-linux-gnueabi-gcc -static -O2 -o vhci_stpbt_bridge vhci_stpbt_bridge.c
 *
 * Usage:
 *   ./vhci_stpbt_bridge
 *
 * Author: Lucas Zampieri <lzampier@redhat.com>
 * License: GPL-2.0
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <signal.h>

#define VHCI_DEV    "/dev/vhci"
#define STPBT_DEV   "/dev/stpbt"
#define BUF_SIZE    4096

/* HCI packet types (H4 protocol) */
#define HCI_COMMAND_PKT     0x01
#define HCI_ACLDATA_PKT     0x02
#define HCI_SCODATA_PKT     0x03
#define HCI_EVENT_PKT       0x04
#define HCI_VENDOR_PKT      0xff

/* VHCI specific vendor commands */
#define HCI_VHCI_PKT        0xff
#define VHCI_OP_WRITE       0x01

static volatile int running = 1;

static void signal_handler(int sig)
{
    (void)sig;
    running = 0;
}

static int set_nonblocking(int fd)
{
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0)
        return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

/* Get the expected packet length based on H4 packet type */
static int get_packet_len(const unsigned char *buf, int len, int *is_vhci_internal)
{
    *is_vhci_internal = 0;

    if (len < 1)
        return 0;

    switch (buf[0]) {
    case HCI_COMMAND_PKT:
        /* 1 (type) + 2 (opcode) + 1 (param_len) + param_len */
        if (len < 4)
            return 0;
        return 4 + buf[3];

    case HCI_ACLDATA_PKT:
        /* 1 (type) + 2 (handle) + 2 (data_len) + data_len */
        if (len < 5)
            return 0;
        return 5 + (buf[3] | (buf[4] << 8));

    case HCI_SCODATA_PKT:
        /* 1 (type) + 2 (handle) + 1 (data_len) + data_len */
        if (len < 4)
            return 0;
        return 4 + buf[3];

    case HCI_EVENT_PKT:
        /* 1 (type) + 1 (event) + 1 (param_len) + param_len */
        if (len < 3)
            return 0;
        return 3 + buf[2];

    case HCI_VHCI_PKT:
        /*
         * VHCI vendor packets - these are internal to the VHCI driver
         * and should NOT be forwarded to the real BT chip.
         * Format: 0xff + opcode(1) + data
         * Common: 0xff 0x01 = VHCI_OP_WRITE (config)
         */
        *is_vhci_internal = 1;
        if (len < 2)
            return 0;
        /* Vendor packets vary in size - consume what we have */
        return len;

    default:
        fprintf(stderr, "Unknown packet type: 0x%02x\n", buf[0]);
        return -1;
    }
}

static void print_hex(const char *prefix, const unsigned char *buf, int len)
{
    int i;
    printf("%s (%d bytes): ", prefix, len);
    for (i = 0; i < len && i < 32; i++)
        printf("%02x ", buf[i]);
    if (len > 32)
        printf("...");
    printf("\n");
    fflush(stdout);
}

int main(int argc, char *argv[])
{
    int vhci_fd = -1;
    int stpbt_fd = -1;
    int ret = 1;
    int verbose = 0;
    unsigned char vhci_buf[BUF_SIZE];
    unsigned char stpbt_buf[BUF_SIZE];
    int vhci_len = 0;
    int stpbt_len = 0;

    /* Check for verbose flag */
    if (argc > 1 && strcmp(argv[1], "-v") == 0)
        verbose = 1;

    /* Set up signal handlers */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    printf("VHCI-stpbt Bridge for Kindle MediaTek BT\n");
    printf("=========================================\n");

    /* Open VHCI device - this creates a virtual HCI adapter */
    printf("Opening %s...\n", VHCI_DEV);
    vhci_fd = open(VHCI_DEV, O_RDWR);
    if (vhci_fd < 0) {
        perror("Failed to open /dev/vhci");
        fprintf(stderr, "Make sure hci_vhci module is loaded\n");
        goto cleanup;
    }
    printf("VHCI opened successfully (fd=%d)\n", vhci_fd);

    /* Give kernel time to create the HCI device */
    usleep(100000);

    /* Open stpbt device */
    printf("Opening %s...\n", STPBT_DEV);
    stpbt_fd = open(STPBT_DEV, O_RDWR);
    if (stpbt_fd < 0) {
        perror("Failed to open /dev/stpbt");
        fprintf(stderr, "Make sure BT function is enabled via WMT\n");
        fprintf(stderr, "And that no other process has the device open\n");
        goto cleanup;
    }
    printf("stpbt opened successfully (fd=%d)\n", stpbt_fd);

    /* Set non-blocking mode */
    if (set_nonblocking(vhci_fd) < 0 || set_nonblocking(stpbt_fd) < 0) {
        perror("Failed to set non-blocking mode");
        goto cleanup;
    }

    printf("\nBridge running. Press Ctrl+C to stop.\n");
    printf("Check /sys/class/bluetooth/ for hci0 device.\n\n");

    /* Main loop - proxy data between vhci and stpbt */
    while (running) {
        fd_set rfds;
        struct timeval tv;
        int maxfd;
        int n;

        FD_ZERO(&rfds);
        FD_SET(vhci_fd, &rfds);
        FD_SET(stpbt_fd, &rfds);
        maxfd = (vhci_fd > stpbt_fd) ? vhci_fd : stpbt_fd;

        tv.tv_sec = 1;
        tv.tv_usec = 0;

        n = select(maxfd + 1, &rfds, NULL, NULL, &tv);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            perror("select");
            break;
        }
        if (n == 0)
            continue;  /* timeout */

        /* Read from VHCI (host -> controller) */
        if (FD_ISSET(vhci_fd, &rfds)) {
            n = read(vhci_fd, vhci_buf + vhci_len, BUF_SIZE - vhci_len);
            if (n > 0) {
                vhci_len += n;

                /* Process complete packets */
                while (vhci_len > 0) {
                    int is_vhci_internal = 0;
                    int pkt_len = get_packet_len(vhci_buf, vhci_len, &is_vhci_internal);
                    if (pkt_len <= 0)
                        break;
                    if (pkt_len > vhci_len)
                        break;  /* need more data */

                    if (is_vhci_internal) {
                        /* VHCI internal packet - don't forward to BT chip */
                        if (verbose)
                            print_hex("VHCI internal (ignored)", vhci_buf, pkt_len);
                    } else {
                        if (verbose)
                            print_hex("TX->chip", vhci_buf, pkt_len);

                        /* Write packet to stpbt */
                        if (write(stpbt_fd, vhci_buf, pkt_len) != pkt_len) {
                            perror("write to stpbt");
                        }
                    }

                    /* Remove processed packet from buffer */
                    if (pkt_len < vhci_len)
                        memmove(vhci_buf, vhci_buf + pkt_len, vhci_len - pkt_len);
                    vhci_len -= pkt_len;
                }
            } else if (n < 0 && errno != EAGAIN) {
                perror("read from vhci");
            }
        }

        /* Read from stpbt (controller -> host) */
        if (FD_ISSET(stpbt_fd, &rfds)) {
            n = read(stpbt_fd, stpbt_buf + stpbt_len, BUF_SIZE - stpbt_len);
            if (n > 0) {
                stpbt_len += n;

                /* Process complete packets */
                while (stpbt_len > 0) {
                    int is_vhci_internal = 0;
                    int pkt_len = get_packet_len(stpbt_buf, stpbt_len, &is_vhci_internal);
                    if (pkt_len <= 0)
                        break;
                    if (pkt_len > stpbt_len)
                        break;  /* need more data */

                    if (verbose)
                        print_hex("RX<-chip", stpbt_buf, pkt_len);

                    /* Write packet to vhci */
                    if (write(vhci_fd, stpbt_buf, pkt_len) != pkt_len) {
                        perror("write to vhci");
                    }

                    /* Remove processed packet from buffer */
                    if (pkt_len < stpbt_len)
                        memmove(stpbt_buf, stpbt_buf + pkt_len, stpbt_len - pkt_len);
                    stpbt_len -= pkt_len;
                }
            } else if (n < 0 && errno != EAGAIN) {
                perror("read from stpbt");
            }
        }
    }

    printf("\nShutting down bridge...\n");
    ret = 0;

cleanup:
    if (stpbt_fd >= 0)
        close(stpbt_fd);
    if (vhci_fd >= 0)
        close(vhci_fd);

    return ret;
}
