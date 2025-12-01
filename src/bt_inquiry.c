/*
 * Bluetooth inquiry using HCI ioctl interface
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <errno.h>

#define AF_BLUETOOTH 31
#define BTPROTO_HCI 1

struct sockaddr_hci {
    unsigned short hci_family;
    unsigned short hci_dev;
    unsigned short hci_channel;
};

/* Inquiry info structure */
struct inquiry_info {
    unsigned char bdaddr[6];
    unsigned char pscan_rep_mode;
    unsigned char pscan_period_mode;
    unsigned char pscan_mode;
    unsigned char dev_class[3];
    unsigned short clock_offset;
} __attribute__((packed));

struct hci_inquiry_req {
    unsigned short dev_id;
    unsigned short flags;
    unsigned char lap[3];
    unsigned char length;
    unsigned char num_rsp;
};

/* HCIINQUIRY = _IOR('H', 240, int) */
#define HCIINQUIRY 0x800448f0

/* Inquiry flags */
#define IREQ_CACHE_FLUSH 0x0001

static void print_bdaddr(unsigned char *addr)
{
    printf("%02X:%02X:%02X:%02X:%02X:%02X",
           addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]);
}

static const char *get_device_class(unsigned char *dc)
{
    int major = (dc[1] >> 2) & 0x1f;
    switch (major) {
    case 0: return "Miscellaneous";
    case 1: return "Computer";
    case 2: return "Phone";
    case 3: return "LAN/Network";
    case 4: return "Audio/Video";
    case 5: return "Peripheral";
    case 6: return "Imaging";
    case 7: return "Wearable";
    case 8: return "Toy";
    case 9: return "Health";
    default: return "Unknown";
    }
}

int main(int argc, char *argv[])
{
    int fd;
    int dev_id = 0;
    struct hci_inquiry_req ir;
    struct inquiry_info *info;
    int num_rsp = 20;  /* Max responses */
    int length = 8;    /* Inquiry duration: 8 * 1.28s = 10.24s */
    int i;

    if (argc > 1)
        dev_id = atoi(argv[1]);

    printf("Bluetooth Inquiry Scanner\n");
    printf("=========================\n\n");

    fd = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    /* Allocate buffer for responses */
    info = malloc(num_rsp * sizeof(struct inquiry_info));
    if (!info) {
        perror("malloc");
        close(fd);
        return 1;
    }
    memset(info, 0, num_rsp * sizeof(struct inquiry_info));

    /* Set up inquiry request */
    memset(&ir, 0, sizeof(ir));
    ir.dev_id = dev_id;
    ir.flags = IREQ_CACHE_FLUSH;  /* Flush cache, get fresh results */
    ir.lap[0] = 0x33;  /* GIAC */
    ir.lap[1] = 0x8b;
    ir.lap[2] = 0x9e;
    ir.length = length;
    ir.num_rsp = num_rsp;

    printf("Scanning for %0.1f seconds...\n", length * 1.28);
    printf("Make sure nearby Bluetooth devices are discoverable!\n\n");

    /* Copy info pointer after the hci_inquiry_req struct */
    /* This is how BlueZ does it - the kernel expects the buffer after the request */
    unsigned char *buf = malloc(sizeof(ir) + num_rsp * sizeof(struct inquiry_info));
    memcpy(buf, &ir, sizeof(ir));

    if (ioctl(fd, HCIINQUIRY, buf) < 0) {
        perror("HCIINQUIRY failed");
        printf("errno=%d\n", errno);
        free(buf);
        free(info);
        close(fd);
        return 1;
    }

    /* Get number of responses from the returned structure */
    struct hci_inquiry_req *rp = (struct hci_inquiry_req *)buf;
    int found = rp->num_rsp;
    memcpy(info, buf + sizeof(ir), found * sizeof(struct inquiry_info));

    printf("Found %d device(s):\n\n", found);

    for (i = 0; i < found; i++) {
        printf("Device %d:\n", i + 1);
        printf("  Address: ");
        print_bdaddr(info[i].bdaddr);
        printf("\n");
        printf("  Class: %s (%02x:%02x:%02x)\n",
               get_device_class(info[i].dev_class),
               info[i].dev_class[2], info[i].dev_class[1], info[i].dev_class[0]);
        printf("\n");
    }

    if (found == 0) {
        printf("No devices found. Make sure nearby devices are in discoverable mode.\n");
    }

    free(buf);
    free(info);
    close(fd);
    return 0;
}
