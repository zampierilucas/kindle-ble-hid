/*
 * Bluetooth connection tool for Kindle
 * Creates ACL connection to remote device
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <poll.h>

#define AF_BLUETOOTH 31
#define BTPROTO_HCI 1

/* HCI packet types */
#define HCI_COMMAND_PKT 0x01
#define HCI_EVENT_PKT   0x04

/* HCI commands - OGF | OCF */
#define HCI_OP_CREATE_CONN       0x0405  /* OGF=1, OCF=5 */
#define HCI_OP_DISCONNECT        0x0406  /* OGF=1, OCF=6 */
#define HCI_OP_ACCEPT_CONN_REQ   0x0409  /* OGF=1, OCF=9 */
#define HCI_OP_AUTH_REQUESTED    0x0411  /* OGF=1, OCF=17 */
#define HCI_OP_SET_CONN_ENCRYPT  0x0413  /* OGF=1, OCF=19 */
#define HCI_OP_REMOTE_NAME_REQ   0x0419  /* OGF=1, OCF=25 */
#define HCI_OP_READ_REMOTE_FEATURES 0x041b

/* HCI events */
#define HCI_EV_CONN_COMPLETE     0x03
#define HCI_EV_CONN_REQUEST      0x04
#define HCI_EV_DISCONN_COMPLETE  0x05
#define HCI_EV_AUTH_COMPLETE     0x06
#define HCI_EV_REMOTE_NAME       0x07
#define HCI_EV_ENCRYPT_CHANGE    0x08
#define HCI_EV_CMD_COMPLETE      0x0e
#define HCI_EV_CMD_STATUS        0x0f
#define HCI_EV_PIN_CODE_REQ      0x16
#define HCI_EV_LINK_KEY_REQ      0x17
#define HCI_EV_LINK_KEY_NOTIFY   0x18
#define HCI_EV_IO_CAPABILITY_REQ 0x31
#define HCI_EV_USER_CONFIRM_REQ  0x33
#define HCI_EV_SIMPLE_PAIRING_COMPLETE 0x36

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

    printf("Sending command 0x%04x, %d bytes\n", opcode, plen);
    return write(fd, buf, len);
}

static void process_event(unsigned char *buf, int len, int *conn_handle, int *done)
{
    unsigned char event = buf[1];
    unsigned char plen = buf[2];
    unsigned char *data = buf + 3;

    switch (event) {
    case HCI_EV_CMD_STATUS:
        printf("Command status: status=%d, opcode=0x%04x\n",
               data[0], data[2] | (data[3] << 8));
        if (data[0] != 0) {
            printf("Command failed!\n");
            *done = 1;
        }
        break;

    case HCI_EV_CMD_COMPLETE:
        printf("Command complete: opcode=0x%04x, status=%d\n",
               data[1] | (data[2] << 8), data[3]);
        break;

    case HCI_EV_CONN_COMPLETE:
        printf("Connection complete!\n");
        printf("  Status: %d\n", data[0]);
        *conn_handle = data[1] | (data[2] << 8);
        printf("  Handle: 0x%04x\n", *conn_handle);
        printf("  Address: ");
        print_bdaddr(data + 3);
        printf("\n");
        printf("  Link type: %d (%s)\n", data[9],
               data[9] == 1 ? "ACL" : data[9] == 0 ? "SCO" : "eSCO");
        printf("  Encryption: %d\n", data[10]);
        if (data[0] == 0) {
            printf("\n*** CONNECTION ESTABLISHED ***\n");
        } else {
            printf("\n*** CONNECTION FAILED ***\n");
            *done = 1;
        }
        break;

    case HCI_EV_DISCONN_COMPLETE:
        printf("Disconnection complete: handle=0x%04x, reason=%d\n",
               data[1] | (data[2] << 8), data[3]);
        *done = 1;
        break;

    case HCI_EV_CONN_REQUEST:
        printf("Incoming connection request from ");
        print_bdaddr(data);
        printf("\n");
        printf("  Class: %02x%02x%02x\n", data[6], data[7], data[8]);
        printf("  Link type: %d\n", data[9]);
        break;

    case HCI_EV_REMOTE_NAME:
        printf("Remote name response:\n");
        printf("  Status: %d\n", data[0]);
        printf("  Address: ");
        print_bdaddr(data + 1);
        printf("\n");
        if (data[0] == 0) {
            char name[249];
            memcpy(name, data + 7, 248);
            name[248] = '\0';
            printf("  Name: %s\n", name);
        }
        break;

    case HCI_EV_PIN_CODE_REQ:
        printf("\n*** PIN CODE REQUEST ***\n");
        printf("Device ");
        print_bdaddr(data);
        printf(" is requesting a PIN code.\n");
        printf("Legacy pairing required - need to send PIN code reply.\n");
        break;

    case HCI_EV_LINK_KEY_REQ:
        printf("\n*** LINK KEY REQUEST ***\n");
        printf("Device ");
        print_bdaddr(data);
        printf(" is requesting link key.\n");
        printf("No stored link key - will need to pair.\n");
        break;

    case HCI_EV_LINK_KEY_NOTIFY:
        printf("\n*** LINK KEY NOTIFICATION ***\n");
        printf("New link key for ");
        print_bdaddr(data);
        printf("\n");
        printf("Key type: %d\n", data[22]);
        break;

    case HCI_EV_IO_CAPABILITY_REQ:
        printf("\n*** IO CAPABILITY REQUEST ***\n");
        printf("Device ");
        print_bdaddr(data);
        printf(" wants to pair (SSP).\n");
        break;

    case HCI_EV_USER_CONFIRM_REQ:
        printf("\n*** USER CONFIRMATION REQUEST ***\n");
        printf("Device ");
        print_bdaddr(data);
        printf("\n");
        {
            unsigned int passkey = data[6] | (data[7] << 8) |
                                   (data[8] << 16) | (data[9] << 24);
            printf("Confirm passkey: %06u\n", passkey);
        }
        break;

    case HCI_EV_SIMPLE_PAIRING_COMPLETE:
        printf("Simple Pairing complete: status=%d\n", data[0]);
        break;

    case HCI_EV_AUTH_COMPLETE:
        printf("Authentication complete: status=%d, handle=0x%04x\n",
               data[0], data[1] | (data[2] << 8));
        break;

    case HCI_EV_ENCRYPT_CHANGE:
        printf("Encryption change: status=%d, handle=0x%04x, enabled=%d\n",
               data[0], data[1] | (data[2] << 8), data[3]);
        break;

    default:
        printf("Event 0x%02x (len=%d)\n", event, plen);
        break;
    }
}

int main(int argc, char *argv[])
{
    int fd;
    int dev_id = 0;
    unsigned char bdaddr[6];
    unsigned char buf[256];
    int len;
    int conn_handle = -1;
    int done = 0;

    if (argc < 2) {
        printf("Usage: %s <bdaddr> [hci_dev]\n", argv[0]);
        printf("  bdaddr: Bluetooth address (e.g., 48:01:C5:02:5C:09)\n");
        printf("  hci_dev: HCI device number (default: 0)\n");
        return 1;
    }

    if (parse_bdaddr(argv[1], bdaddr) < 0) {
        fprintf(stderr, "Invalid Bluetooth address: %s\n", argv[1]);
        return 1;
    }

    if (argc > 2)
        dev_id = atoi(argv[2]);

    printf("Bluetooth Connection Tool\n");
    printf("=========================\n\n");

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
    printf("...\n\n");

    /* First, request remote name */
    printf("Requesting remote device name...\n");
    unsigned char name_params[10];
    memcpy(name_params, bdaddr, 6);
    name_params[6] = 0x02;  /* Page scan repetition mode */
    name_params[7] = 0x00;  /* Reserved */
    name_params[8] = 0x00;  /* Clock offset */
    name_params[9] = 0x00;
    send_cmd(fd, HCI_OP_REMOTE_NAME_REQ, name_params, 10);

    /* Wait for name response */
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = POLLIN;

    int name_timeout = 5000;
    while (name_timeout > 0) {
        int ret = poll(&pfd, 1, 1000);
        if (ret < 0) {
            perror("poll");
            break;
        }
        if (ret == 0) {
            name_timeout -= 1000;
            continue;
        }

        len = read(fd, buf, sizeof(buf));
        if (len > 0 && buf[0] == HCI_EVENT_PKT) {
            process_event(buf, len, &conn_handle, &done);
            if (buf[1] == HCI_EV_REMOTE_NAME)
                break;
        }
    }

    /* Create ACL connection */
    printf("\nCreating ACL connection...\n");
    unsigned char conn_params[13];
    memcpy(conn_params, bdaddr, 6);
    conn_params[6] = 0x18;  /* Packet type: DM1, DH1 */
    conn_params[7] = 0xcc;
    conn_params[8] = 0x02;  /* Page scan repetition mode */
    conn_params[9] = 0x00;  /* Reserved */
    conn_params[10] = 0x00; /* Clock offset */
    conn_params[11] = 0x00;
    conn_params[12] = 0x01; /* Allow role switch */
    send_cmd(fd, HCI_OP_CREATE_CONN, conn_params, 13);

    /* Listen for events */
    int timeout = 30000;  /* 30 second timeout */
    while (!done && timeout > 0) {
        int ret = poll(&pfd, 1, 1000);
        if (ret < 0) {
            perror("poll");
            break;
        }
        if (ret == 0) {
            timeout -= 1000;
            printf(".");
            fflush(stdout);
            continue;
        }

        len = read(fd, buf, sizeof(buf));
        if (len < 0) {
            if (errno == EAGAIN)
                continue;
            perror("read");
            break;
        }

        if (len > 0 && buf[0] == HCI_EVENT_PKT) {
            process_event(buf, len, &conn_handle, &done);
        }
    }

    if (timeout <= 0) {
        printf("\nConnection timeout!\n");
    }

    if (conn_handle >= 0) {
        printf("\nConnection handle: 0x%04x\n", conn_handle);
        printf("Press Enter to disconnect...\n");
        getchar();

        /* Disconnect */
        unsigned char disc_params[3];
        disc_params[0] = conn_handle & 0xff;
        disc_params[1] = conn_handle >> 8;
        disc_params[2] = 0x13;  /* Remote user terminated */
        send_cmd(fd, HCI_OP_DISCONNECT, disc_params, 3);

        /* Wait for disconnect */
        done = 0;
        while (!done) {
            int ret = poll(&pfd, 1, 5000);
            if (ret <= 0)
                break;
            len = read(fd, buf, sizeof(buf));
            if (len > 0 && buf[0] == HCI_EVENT_PKT)
                process_event(buf, len, &conn_handle, &done);
        }
    }

    close(fd);
    return 0;
}
