/*
 * Simple Bluetooth device scanner for Kindle
 * Performs inquiry scan to find nearby devices
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
#define HCI_VENDOR_PKT  0xff

/* HCI commands */
#define HCI_OP_INQUIRY           0x0401
#define HCI_OP_INQUIRY_CANCEL    0x0402
#define HCI_OP_WRITE_SCAN_ENABLE 0x0c1a
#define HCI_OP_LE_SET_SCAN_PARAM 0x200b
#define HCI_OP_LE_SET_SCAN_EN    0x200c

/* HCI events */
#define HCI_EV_INQUIRY_RESULT    0x02
#define HCI_EV_INQUIRY_COMPLETE  0x01
#define HCI_EV_CMD_COMPLETE      0x0e
#define HCI_EV_CMD_STATUS        0x0f
#define HCI_EV_LE_META           0x3e
#define HCI_EV_EXT_INQ_RESULT    0x2f

/* LE Meta events */
#define HCI_EV_LE_ADVERTISING_REPORT 0x02

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

#define HCI_FLT_TYPE_BITS  31
#define HCI_FLT_EVENT_BITS 63

static void hci_set_bit(int nr, void *addr)
{
    *((unsigned int *) addr + (nr >> 5)) |= (1 << (nr & 31));
}

static void hci_filter_clear(struct hci_filter *f)
{
    memset(f, 0, sizeof(*f));
}

static void hci_filter_set_ptype(int t, struct hci_filter *f)
{
    hci_set_bit(t == HCI_VENDOR_PKT ? 0 : t, &f->type_mask);
}

static void hci_filter_set_event(int e, struct hci_filter *f)
{
    hci_set_bit(e, f->event_mask);
}

static void hci_filter_all_ptypes(struct hci_filter *f)
{
    memset(&f->type_mask, 0xff, sizeof(f->type_mask));
}

static void hci_filter_all_events(struct hci_filter *f)
{
    memset(f->event_mask, 0xff, sizeof(f->event_mask));
}

#define SOL_HCI   0
#define HCI_FILTER 2

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

static int send_cmd(int fd, unsigned short ogf, unsigned short ocf, 
                   unsigned char *params, int plen)
{
    unsigned char buf[256];
    unsigned short opcode = (ogf << 10) | ocf;
    int len = 4 + plen;

    buf[0] = HCI_COMMAND_PKT;
    buf[1] = opcode & 0xff;
    buf[2] = opcode >> 8;
    buf[3] = plen;
    if (plen)
        memcpy(buf + 4, params, plen);

    return write(fd, buf, len);
}

static void process_event(unsigned char *buf, int len)
{
    unsigned char event = buf[1];
    unsigned char plen = buf[2];
    unsigned char *data = buf + 3;

    switch (event) {
    case HCI_EV_INQUIRY_RESULT:
        {
            int num = data[0];
            int i;
            printf("Inquiry result: %d device(s)\n", num);
            data++;
            for (i = 0; i < num; i++) {
                printf("  Device %d: ", i+1);
                print_bdaddr(data);
                printf(" (Class: %02x%02x%02x)\n",
                       data[9], data[10], data[11]);
                data += 14;
            }
        }
        break;

    case HCI_EV_EXT_INQ_RESULT:
        printf("Extended inquiry result:\n");
        printf("  Address: ");
        print_bdaddr(data + 1);
        printf("\n  RSSI: %d dBm\n", (signed char)data[14]);
        break;

    case HCI_EV_INQUIRY_COMPLETE:
        printf("Inquiry complete (status: %d)\n", data[0]);
        break;

    case HCI_EV_CMD_COMPLETE:
        printf("Command complete: opcode=0x%04x status=%d\n",
               data[1] | (data[2] << 8), data[3]);
        break;

    case HCI_EV_CMD_STATUS:
        printf("Command status: status=%d opcode=0x%04x\n",
               data[0], data[2] | (data[3] << 8));
        break;

    case HCI_EV_LE_META:
        if (data[0] == HCI_EV_LE_ADVERTISING_REPORT) {
            int num = data[1];
            int i;
            unsigned char *ptr = data + 2;
            printf("LE Advertising report: %d device(s)\n", num);
            for (i = 0; i < num; i++) {
                unsigned char evt_type = ptr[0];
                unsigned char addr_type = ptr[1];
                printf("  Device %d: ", i+1);
                print_bdaddr(ptr + 2);
                printf(" (type=%d, evt=%d", addr_type, evt_type);
                /* Skip to RSSI */
                int data_len = ptr[8];
                signed char rssi = ptr[9 + data_len];
                printf(", RSSI=%d dBm)\n", rssi);
                ptr += 10 + data_len;
            }
        } else {
            printf("LE Meta event: subevent=%d\n", data[0]);
        }
        break;

    default:
        printf("Event: 0x%02x (len=%d)\n", event, plen);
    }
}

int main(int argc, char *argv[])
{
    int fd;
    int dev_id = 0;
    struct hci_filter flt;
    unsigned char buf[256];
    int len;
    int scan_le = 0;

    if (argc > 1) {
        if (strcmp(argv[1], "-le") == 0)
            scan_le = 1;
        else
            dev_id = atoi(argv[1]);
    }

    printf("Bluetooth Scanner for Kindle\n");
    printf("============================\n\n");

    fd = hci_open_dev(dev_id);
    if (fd < 0) {
        perror("Failed to open HCI device");
        return 1;
    }

    /* Set filter to receive all events */
    hci_filter_clear(&flt);
    hci_filter_all_ptypes(&flt);
    hci_filter_all_events(&flt);
    if (setsockopt(fd, SOL_HCI, HCI_FILTER, &flt, sizeof(flt)) < 0) {
        perror("setsockopt(HCI_FILTER)");
        /* Continue anyway */
    }

    if (scan_le) {
        printf("Starting LE scan...\n");

        /* Set LE scan parameters */
        unsigned char le_params[7] = {
            0x01,       /* scan type: active */
            0x10, 0x00, /* interval: 16 (10ms) */
            0x10, 0x00, /* window: 16 (10ms) */
            0x00,       /* own addr type: public */
            0x00        /* filter: none */
        };
        send_cmd(fd, 0x08, 0x0b, le_params, 7);

        /* Enable LE scan */
        unsigned char le_enable[2] = { 0x01, 0x00 }; /* enable, no duplicates filter */
        send_cmd(fd, 0x08, 0x0c, le_enable, 2);
    } else {
        printf("Starting classic inquiry scan (8 seconds)...\n");

        /* Start inquiry - LAP=GIAC (0x9e8b33), length=8 (10.24s), num_rsp=0 (unlimited) */
        unsigned char inq_params[5] = { 0x33, 0x8b, 0x9e, 0x08, 0x00 };
        send_cmd(fd, 0x01, 0x01, inq_params, 5);
    }

    printf("\nListening for devices...\n\n");

    /* Listen for events */
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = POLLIN;

    int timeout = scan_le ? 10000 : 12000;  /* 10s LE, 12s classic */
    
    while (1) {
        int ret = poll(&pfd, 1, timeout);
        if (ret < 0) {
            perror("poll");
            break;
        }
        if (ret == 0) {
            printf("\nScan timeout\n");
            break;
        }

        len = read(fd, buf, sizeof(buf));
        if (len < 0) {
            if (errno == EAGAIN)
                continue;
            perror("read");
            break;
        }

        if (len > 0 && buf[0] == HCI_EVENT_PKT) {
            process_event(buf, len);
            if (!scan_le && buf[1] == HCI_EV_INQUIRY_COMPLETE)
                break;
        }
    }

    /* Cancel scan */
    if (scan_le) {
        unsigned char le_disable[2] = { 0x00, 0x00 };
        send_cmd(fd, 0x08, 0x0c, le_disable, 2);
    } else {
        send_cmd(fd, 0x01, 0x02, NULL, 0);
    }

    close(fd);
    return 0;
}
