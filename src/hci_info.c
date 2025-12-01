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

#define HCI_UP      (1 << 0)
#define HCI_INIT    (1 << 1)
#define HCI_RUNNING (1 << 2)
#define HCI_PSCAN   (1 << 3)
#define HCI_ISCAN   (1 << 4)
#define HCI_AUTH    (1 << 5)
#define HCI_ENCRYPT (1 << 6)

/* Correct HCI ioctl values using _IOR('H', nr, int) format */
/* _IOR on ARM: (2 << 30) | (4 << 16) | ('H' << 8) | nr */
/* = 0x80000000 | 0x00040000 | 0x00004800 | nr */
/* = 0x80044800 | nr */
#define HCIGETDEVINFO  0x800448d3   /* _IOR('H', 211, int) */

static int hci_open_ctl(void)
{
    int fd;
    struct sockaddr_hci addr;

    fd = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (fd < 0)
        return fd;

    memset(&addr, 0, sizeof(addr));
    addr.hci_family = AF_BLUETOOTH;
    addr.hci_dev = 0xFFFF;
    addr.hci_channel = 0;

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }

    return fd;
}

int main(int argc, char *argv[])
{
    int ctl;
    struct hci_dev_info di;
    int dev_id = 0;

    ctl = hci_open_ctl();
    if (ctl < 0) {
        perror("Can't open HCI socket");
        return 1;
    }

    if (argc > 1)
        dev_id = atoi(argv[1]);

    memset(&di, 0, sizeof(di));
    di.dev_id = dev_id;

    printf("struct size: %zu bytes\n", sizeof(di));
    printf("Using HCIGETDEVINFO = 0x%x\n", HCIGETDEVINFO);

    if (ioctl(ctl, HCIGETDEVINFO, &di) < 0) {
        perror("HCIGETDEVINFO failed");
        printf("errno=%d\n", errno);
        close(ctl);
        return 1;
    }

    printf("\nhci%d:\n", di.dev_id);
    printf("  Name: %s\n", di.name[0] ? di.name : "(empty)");
    printf("  BD Address: %02X:%02X:%02X:%02X:%02X:%02X\n",
           di.bdaddr[5], di.bdaddr[4], di.bdaddr[3],
           di.bdaddr[2], di.bdaddr[1], di.bdaddr[0]);
    printf("  Type: %s\n", di.type == 0 ? "Primary" : "AMP");
    printf("  Flags: 0x%08x", di.flags);
    if (di.flags & HCI_UP) printf(" UP");
    if (di.flags & HCI_INIT) printf(" INIT");
    if (di.flags & HCI_RUNNING) printf(" RUNNING");
    if (di.flags & HCI_PSCAN) printf(" PSCAN");
    if (di.flags & HCI_ISCAN) printf(" ISCAN");
    printf("\n");
    printf("  ACL MTU: %d:%d\n", di.acl_mtu, di.acl_pkts);
    printf("  SCO MTU: %d:%d\n", di.sco_mtu, di.sco_pkts);
    printf("  Features: %02x %02x %02x %02x %02x %02x %02x %02x\n",
           di.features[0], di.features[1], di.features[2], di.features[3],
           di.features[4], di.features[5], di.features[6], di.features[7]);
    printf("  Stats:\n");
    printf("    RX: %u bytes, errors=%u, events=%u, acl=%u, sco=%u\n",
           di.byte_rx, di.err_rx, di.evt_rx, di.acl_rx, di.sco_rx);
    printf("    TX: %u bytes, errors=%u, cmds=%u, acl=%u, sco=%u\n",
           di.byte_tx, di.err_tx, di.cmd_tx, di.acl_tx, di.sco_tx);

    close(ctl);
    return 0;
}
