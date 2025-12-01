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

int main(int argc, char *argv[])
{
    int fd;
    struct sockaddr_hci addr;
    int dev_id = 0;
    
    printf("Testing HCI socket...\n");
    
    /* Create raw HCI socket */
    fd = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    printf("socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI) = %d\n", fd);
    if (fd < 0) {
        perror("  socket failed");
        return 1;
    }
    
    /* Try binding to HCI_DEV_NONE (0xFFFF) first */
    memset(&addr, 0, sizeof(addr));
    addr.hci_family = AF_BLUETOOTH;
    addr.hci_dev = 0xFFFF;  /* HCI_DEV_NONE */
    addr.hci_channel = 0;   /* HCI_CHANNEL_RAW */
    
    printf("Trying bind with hci_dev=0xFFFF (HCI_DEV_NONE)...\n");
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        printf("  bind(0xFFFF) failed: %s (errno=%d)\n", strerror(errno), errno);
        
        /* Try binding to hci0 directly */
        addr.hci_dev = 0;
        printf("Trying bind with hci_dev=0 (hci0)...\n");
        if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
            printf("  bind(0) failed: %s (errno=%d)\n", strerror(errno), errno);
        } else {
            printf("  bind(0) succeeded!\n");
        }
    } else {
        printf("  bind(0xFFFF) succeeded!\n");
    }
    
    /* Try HCIDEVUP ioctl - value 201 from Linux kernel */
    printf("\nTrying HCIDEVUP ioctl on dev 0...\n");
    
    /* On Linux ARM, the ioctl value should be: _IOW('H', 201, int) */
    /* _IOW means write, 'H' = 0x48, 201 = 0xC9 */
    /* ARM uses the same encoding as x86: dir(2) + size(14) + type(8) + nr(8) */
    
    /* For ARM 32-bit: _IOW('H', 201, int) = 0x400448c9 */
    unsigned long hcidevup = 0x400448c9;
    printf("  Using HCIDEVUP = 0x%lx\n", hcidevup);
    
    if (ioctl(fd, hcidevup, dev_id) < 0) {
        printf("  HCIDEVUP failed: %s (errno=%d)\n", strerror(errno), errno);
    } else {
        printf("  HCIDEVUP succeeded!\n");
    }
    
    /* Try HCIGETDEVLIST - value 210 */
    printf("\nTrying HCIGETDEVLIST ioctl...\n");
    struct {
        unsigned short dev_num;
        struct {
            unsigned short dev_id;
            unsigned int dev_opt;
        } dev_req[16];
    } dl;
    
    memset(&dl, 0, sizeof(dl));
    dl.dev_num = 16;
    
    /* _IOR('H', 210, ...) - the size varies but we use a guess */
    unsigned long hcigetdevlist = 0x800448d2;  /* Might need adjustment */
    printf("  Using HCIGETDEVLIST = 0x%lx\n", hcigetdevlist);
    
    if (ioctl(fd, hcigetdevlist, &dl) < 0) {
        printf("  HCIGETDEVLIST failed: %s (errno=%d)\n", strerror(errno), errno);
        
        /* Try without the size in ioctl */
        hcigetdevlist = 0xc00448d2;
        printf("  Trying alternate HCIGETDEVLIST = 0x%lx\n", hcigetdevlist);
        if (ioctl(fd, hcigetdevlist, &dl) < 0) {
            printf("  Still failed: %s (errno=%d)\n", strerror(errno), errno);
        } else {
            printf("  Found %d devices\n", dl.dev_num);
        }
    } else {
        printf("  Found %d devices\n", dl.dev_num);
    }
    
    close(fd);
    return 0;
}
