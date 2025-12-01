/*
 * Minimal HCI tool for Kindle
 * Using proper HCI socket address structure
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <errno.h>

/* Bluetooth protocol family */
#define AF_BLUETOOTH 31
#define PF_BLUETOOTH AF_BLUETOOTH
#define BTPROTO_HCI 1

/* HCI channels */
#define HCI_CHANNEL_RAW     0
#define HCI_CHANNEL_USER    1
#define HCI_CHANNEL_CONTROL 3

/* HCI ioctl defines - use _IOC macros to get correct values */
#define _IOC_NONE  0U
#define _IOC_WRITE 1U
#define _IOC_READ  2U

#define _IOC(dir,type,nr,size) \
    (((dir)  << 30) | \
     ((type) << 8) | \
     ((nr)   << 0) | \
     ((size) << 16))
#define _IOR(type,nr,size)  _IOC(_IOC_READ,(type),(nr),sizeof(size))
#define _IOW(type,nr,size)  _IOC(_IOC_WRITE,(type),(nr),sizeof(size))

#define HCIDEVUP      _IOW('H', 201, int)
#define HCIDEVDOWN    _IOW('H', 202, int)
#define HCIGETDEVLIST _IOR('H', 210, struct hci_dev_list_req)
#define HCIGETDEVINFO _IOR('H', 211, struct hci_dev_info)

#define HCI_MAX_DEV 16

/* Socket address for HCI */
struct sockaddr_hci {
    unsigned short hci_family;
    unsigned short hci_dev;
    unsigned short hci_channel;
};

struct hci_dev_req {
    unsigned short dev_id;
    unsigned int dev_opt;
};

struct hci_dev_list_req {
    unsigned short dev_num;
    struct hci_dev_req dev_req[HCI_MAX_DEV];
};

struct hci_dev_info {
    unsigned short dev_id;
    char name[8];
    unsigned char bdaddr[6];
    unsigned int flags;
    unsigned char type;
    unsigned char features[8];
    unsigned int pkt_type;
    unsigned int link_policy;
    unsigned int link_mode;
    unsigned short acl_mtu;
    unsigned short acl_pkts;
    unsigned short sco_mtu;
    unsigned short sco_pkts;
    unsigned int err_rx;
    unsigned int err_tx;
    unsigned int cmd_tx;
    unsigned int evt_rx;
    unsigned int acl_tx;
    unsigned int acl_rx;
    unsigned int sco_tx;
    unsigned int sco_rx;
    unsigned int byte_rx;
    unsigned int byte_tx;
};

/* HCI device flags */
#define HCI_UP      (1 << 0)
#define HCI_INIT    (1 << 1)
#define HCI_RUNNING (1 << 2)
#define HCI_PSCAN   (1 << 3)
#define HCI_ISCAN   (1 << 4)

static void print_bdaddr(unsigned char *bdaddr)
{
    printf("%02X:%02X:%02X:%02X:%02X:%02X",
           bdaddr[5], bdaddr[4], bdaddr[3],
           bdaddr[2], bdaddr[1], bdaddr[0]);
}

static int hci_open_ctl(void)
{
    int fd;
    struct sockaddr_hci addr;

    fd = socket(AF_BLUETOOTH, SOCK_RAW | SOCK_CLOEXEC, BTPROTO_HCI);
    if (fd < 0)
        return fd;

    memset(&addr, 0, sizeof(addr));
    addr.hci_family = AF_BLUETOOTH;
    addr.hci_dev = 0xFFFF;  /* HCI_DEV_NONE */
    addr.hci_channel = HCI_CHANNEL_RAW;

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        int err = errno;
        close(fd);
        errno = err;
        return -1;
    }

    return fd;
}

int main(int argc, char *argv[])
{
    int ctl, dev_id = 0;
    struct hci_dev_list_req dl;
    struct hci_dev_info di;
    int i;

    ctl = hci_open_ctl();
    if (ctl < 0) {
        perror("Can't open HCI socket");
        printf("errno=%d\n", errno);
        return 1;
    }

    /* Handle commands */
    if (argc >= 2) {
        if (argc >= 3) {
            dev_id = atoi(argv[2]);
        }

        if (strcmp(argv[1], "up") == 0) {
            printf("Bringing hci%d up...\n", dev_id);
            if (ioctl(ctl, HCIDEVUP, dev_id) < 0) {
                if (errno == EALREADY) {
                    printf("Device is already up\n");
                } else {
                    perror("HCIDEVUP failed");
                    printf("errno=%d ioctl=0x%x\n", errno, HCIDEVUP);
                    close(ctl);
                    return 1;
                }
            } else {
                printf("hci%d is now UP\n", dev_id);
            }
            close(ctl);
            return 0;
        }

        if (strcmp(argv[1], "down") == 0) {
            printf("Bringing hci%d down...\n", dev_id);
            if (ioctl(ctl, HCIDEVDOWN, dev_id) < 0) {
                perror("HCIDEVDOWN failed");
                close(ctl);
                return 1;
            }
            printf("hci%d is now DOWN\n", dev_id);
            close(ctl);
            return 0;
        }
    }

    /* List devices */
    memset(&dl, 0, sizeof(dl));
    dl.dev_num = HCI_MAX_DEV;

    if (ioctl(ctl, HCIGETDEVLIST, &dl) < 0) {
        perror("Can't get device list");
        printf("errno=%d ioctl=0x%x\n", errno, HCIGETDEVLIST);
        close(ctl);
        return 1;
    }

    if (dl.dev_num == 0) {
        printf("No HCI devices found\n");
        close(ctl);
        return 0;
    }

    printf("Found %d HCI device(s):\n\n", dl.dev_num);

    for (i = 0; i < dl.dev_num; i++) {
        memset(&di, 0, sizeof(di));
        di.dev_id = dl.dev_req[i].dev_id;

        if (ioctl(ctl, HCIGETDEVINFO, &di) < 0) {
            perror("HCIGETDEVINFO failed");
            continue;
        }

        printf("hci%d:\n", di.dev_id);
        printf("  Name: %s\n", di.name);
        printf("  Type: %s\n", di.type == 0 ? "Primary" : "AMP");
        printf("  BD Address: ");
        print_bdaddr(di.bdaddr);
        printf("\n");
        printf("  Flags: 0x%08x", di.flags);
        if (di.flags & HCI_UP) printf(" UP");
        if (di.flags & HCI_INIT) printf(" INIT");
        if (di.flags & HCI_RUNNING) printf(" RUNNING");
        if (di.flags & HCI_PSCAN) printf(" PSCAN");
        if (di.flags & HCI_ISCAN) printf(" ISCAN");
        printf("\n");
        printf("  ACL MTU: %d:%d  SCO MTU: %d:%d\n",
               di.acl_mtu, di.acl_pkts, di.sco_mtu, di.sco_pkts);
        printf("  RX bytes: %u  TX bytes: %u\n", di.byte_rx, di.byte_tx);
        printf("\n");
    }

    close(ctl);
    return 0;
}
