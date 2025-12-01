/*
 * BLE connection tool for Kindle
 * Connects to a BLE device and maintains the connection
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>

#define AF_BLUETOOTH 31
#define BTPROTO_HCI 1

/* HCI packet types */
#define HCI_COMMAND_PKT 0x01
#define HCI_EVENT_PKT   0x04

/* HCI LE commands */
#define HCI_OP_LE_SET_SCAN_ENABLE       0x200c
#define HCI_OP_LE_CREATE_CONN           0x200d
#define HCI_OP_LE_CREATE_CONN_CANCEL    0x200e
#define HCI_OP_DISCONNECT               0x0406

/* HCI events */
#define HCI_EV_DISCONN_COMPLETE         0x05
#define HCI_EV_CMD_COMPLETE             0x0e
#define HCI_EV_CMD_STATUS               0x0f
#define HCI_EV_LE_META                  0x3e

/* LE Meta events */
#define HCI_EV_LE_CONN_COMPLETE         0x01
#define HCI_EV_LE_ADVERTISING_REPORT    0x02

struct sockaddr_hci {
    unsigned short hci_family;
    unsigned short hci_dev;
    unsigned short hci_channel;
};

struct hci_filter {
    unsigned int type_mask;
    unsigned int event_mask[2];
    unsigned short opcode;
};

#define SOL_HCI    0
#define HCI_FILTER 2

static volatile int keep_running = 1;

static void sig_handler(int sig)
{
    keep_running = 0;
}

static void hci_set_bit(int nr, void *addr)
{
    *((unsigned int *)addr + (nr >> 5)) |= (1 << (nr & 31));
}

static int hci_open_dev(int dev_id)
{
    int fd;
    struct sockaddr_hci addr;

    fd = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (fd < 0)
        return fd;

    memset(&addr, 0, sizeof(addr));
    addr.hci_family = AF_BLUETOOTH;
    addr.hci_dev = dev_id;
    addr.hci_channel = 0;

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }

    return fd;
}

static void print_bdaddr(unsigned char *addr)
{
    printf("%02X:%02X:%02X:%02X:%02X:%02X",
           addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]);
}

static int parse_bdaddr(const char *str, unsigned char *addr)
{
    int v[6];
    if (sscanf(str, "%x:%x:%x:%x:%x:%x",
               &v[5], &v[4], &v[3], &v[2], &v[1], &v[0]) != 6)
        return -1;
    for (int i = 0; i < 6; i++)
        addr[i] = v[i];
    return 0;
}

static int send_cmd(int fd, unsigned short opcode,
                   unsigned char *params, int plen)
{
    unsigned char buf[256];
    int len = 4 + plen;

    buf[0] = HCI_COMMAND_PKT;
    buf[1] = opcode & 0xff;
    buf[2] = opcode >> 8;
    buf[3] = plen;
    if (plen)
        memcpy(buf + 4, params, plen);

    return write(fd, buf, len);
}

static void process_event(unsigned char *buf, int len,
                         int *conn_handle, int *connected, int *done)
{
    unsigned char event = buf[1];
    unsigned char plen = buf[2];
    unsigned char *data = buf + 3;

    switch (event) {
    case HCI_EV_CMD_STATUS:
        printf("Command status: status=%d, opcode=0x%04x\n",
               data[0], data[2] | (data[3] << 8));
        if (data[0] != 0) {
            printf("Command failed with status %d\n", data[0]);
            if ((data[2] | (data[3] << 8)) == HCI_OP_LE_CREATE_CONN) {
                *done = 1;
            }
        }
        break;

    case HCI_EV_CMD_COMPLETE:
        {
            unsigned short opcode = data[1] | (data[2] << 8);
            unsigned char status = data[3];
            if (opcode == HCI_OP_LE_SET_SCAN_ENABLE) {
                printf("LE scan %s (status=%d)\n",
                       status == 0 ? "stopped" : "stop failed", status);
            }
        }
        break;

    case HCI_EV_DISCONN_COMPLETE:
        printf("\nDisconnection complete:\n");
        printf("  Status: %d\n", data[0]);
        printf("  Handle: 0x%04x\n", data[1] | (data[2] << 8));
        printf("  Reason: %d\n", data[3]);
        *connected = 0;
        *done = 1;
        break;

    case HCI_EV_LE_META:
        {
            unsigned char subevent = data[0];
            switch (subevent) {
            case HCI_EV_LE_CONN_COMPLETE:
                printf("\n*** LE CONNECTION COMPLETE ***\n");
                printf("  Status: %d\n", data[1]);
                if (data[1] == 0) {
                    *conn_handle = data[2] | (data[3] << 8);
                    printf("  Handle: 0x%04x\n", *conn_handle);
                    printf("  Peer address: ");
                    print_bdaddr(data + 5);
                    printf("\n");
                    printf("  Peer address type: %d\n", data[4]);
                    printf("  Connection interval: %d (%.2f ms)\n",
                           data[11] | (data[12] << 8),
                           (data[11] | (data[12] << 8)) * 1.25);
                    printf("  Connection latency: %d\n",
                           data[13] | (data[14] << 8));
                    printf("  Supervision timeout: %d (%.0f ms)\n",
                           data[15] | (data[16] << 8),
                           (data[15] | (data[16] << 8)) * 10.0);
                    printf("\n*** CONNECTION ESTABLISHED ***\n");
                    printf("Press Ctrl+C to disconnect\n\n");
                    *connected = 1;
                } else {
                    printf("  Connection failed with status %d\n", data[1]);
                    *done = 1;
                }
                break;

            case HCI_EV_LE_ADVERTISING_REPORT:
                /* Ignore advertising reports during connection */
                break;

            default:
                printf("LE Meta event: subevent=0x%02x\n", subevent);
                break;
            }
        }
        break;

    default:
        /* Silently ignore other events */
        break;
    }
}

int main(int argc, char *argv[])
{
    int fd;
    int dev_id = 0;
    unsigned char bdaddr[6];
    unsigned char addr_type = 0;  /* Public address */
    unsigned char buf[256];
    int len;
    int conn_handle = -1;
    int connected = 0;
    int done = 0;

    if (argc < 2) {
        printf("Usage: %s <bdaddr> [addr_type] [hci_dev]\n", argv[0]);
        printf("  bdaddr: BLE device address (e.g., 5C:2B:3E:50:4F:04)\n");
        printf("  addr_type: 0=public (default), 1=random\n");
        printf("  hci_dev: HCI device number (default: 0)\n");
        return 1;
    }

    if (parse_bdaddr(argv[1], bdaddr) < 0) {
        fprintf(stderr, "Invalid Bluetooth address: %s\n", argv[1]);
        return 1;
    }

    if (argc > 2)
        addr_type = atoi(argv[2]);
    if (argc > 3)
        dev_id = atoi(argv[3]);

    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    printf("BLE Connection Tool\n");
    printf("===================\n\n");

    fd = hci_open_dev(dev_id);
    if (fd < 0) {
        perror("Failed to open HCI device");
        return 1;
    }

    /* Set filter to receive all events */
    struct hci_filter flt;
    memset(&flt, 0xff, sizeof(flt));
    if (setsockopt(fd, SOL_HCI, HCI_FILTER, &flt, sizeof(flt)) < 0) {
        perror("setsockopt(HCI_FILTER)");
    }

    printf("Connecting to ");
    print_bdaddr(bdaddr);
    printf(" (type=%d)...\n\n", addr_type);

    /* Stop any ongoing LE scan first */
    unsigned char disable_scan[2] = { 0x00, 0x00 };
    send_cmd(fd, HCI_OP_LE_SET_SCAN_ENABLE, disable_scan, 2);
    usleep(100000);  /* Wait 100ms */

    /* Create LE connection */
    unsigned char conn_params[25];
    memset(conn_params, 0, sizeof(conn_params));

    /* Scan interval and window (60ms) */
    conn_params[0] = 0x60;  /* 96 * 0.625ms = 60ms */
    conn_params[1] = 0x00;
    conn_params[2] = 0x60;
    conn_params[3] = 0x00;

    conn_params[4] = 0x00;  /* Don't use white list */
    conn_params[5] = addr_type;  /* Peer address type */
    memcpy(conn_params + 6, bdaddr, 6);  /* Peer address */
    conn_params[12] = 0x00;  /* Own address type: public */

    /* Connection interval: 24-40 (30-50ms) */
    conn_params[13] = 0x18;  /* Min interval: 24 * 1.25ms = 30ms */
    conn_params[14] = 0x00;
    conn_params[15] = 0x28;  /* Max interval: 40 * 1.25ms = 50ms */
    conn_params[16] = 0x00;

    conn_params[17] = 0x00;  /* Latency: 0 */
    conn_params[18] = 0x00;

    /* Supervision timeout: 420 (4.2s) */
    conn_params[19] = 0xa4;
    conn_params[20] = 0x01;

    /* Min/Max CE length: 0 */
    conn_params[21] = 0x00;
    conn_params[22] = 0x00;
    conn_params[23] = 0x00;
    conn_params[24] = 0x00;

    if (send_cmd(fd, HCI_OP_LE_CREATE_CONN, conn_params, 25) < 0) {
        perror("send LE_CREATE_CONN");
        close(fd);
        return 1;
    }

    /* Listen for events */
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = POLLIN;

    printf("Waiting for connection (timeout: 30s)...\n");
    int timeout_counter = 30000;  /* 30 seconds */

    while (!done && keep_running) {
        int ret = poll(&pfd, 1, 1000);
        if (ret < 0) {
            if (errno == EINTR)
                continue;
            perror("poll");
            break;
        }

        if (ret == 0) {
            if (!connected) {
                timeout_counter -= 1000;
                if (timeout_counter <= 0) {
                    printf("\nConnection timeout!\n");
                    /* Cancel connection attempt */
                    send_cmd(fd, HCI_OP_LE_CREATE_CONN_CANCEL, NULL, 0);
                    done = 1;
                }
                printf(".");
                fflush(stdout);
            }
            continue;
        }

        len = read(fd, buf, sizeof(buf));
        if (len < 0) {
            if (errno == EAGAIN || errno == EINTR)
                continue;
            perror("read");
            break;
        }

        if (len > 0 && buf[0] == HCI_EVENT_PKT) {
            process_event(buf, len, &conn_handle, &connected, &done);
        }

        /* Keep connection alive - just keep reading events */
        if (connected && !done) {
            /* Connection is established, just wait for events or Ctrl+C */
        }
    }

    /* Disconnect if still connected */
    if (connected && conn_handle >= 0) {
        printf("\nDisconnecting...\n");
        unsigned char disc_params[3];
        disc_params[0] = conn_handle & 0xff;
        disc_params[1] = conn_handle >> 8;
        disc_params[2] = 0x13;  /* Remote user terminated */
        send_cmd(fd, HCI_OP_DISCONNECT, disc_params, 3);

        /* Wait for disconnect complete */
        timeout_counter = 5000;
        while (connected && timeout_counter > 0) {
            int ret = poll(&pfd, 1, 100);
            if (ret > 0) {
                len = read(fd, buf, sizeof(buf));
                if (len > 0 && buf[0] == HCI_EVENT_PKT)
                    process_event(buf, len, &conn_handle, &connected, &done);
            }
            timeout_counter -= 100;
        }
    }

    close(fd);
    printf("\nClosed.\n");
    return 0;
}
