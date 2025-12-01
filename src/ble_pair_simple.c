/*
 * Simple BLE pairing tool - attempts connection with Just Works pairing
 * For devices that don't require PIN/passkey
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <errno.h>
#include <poll.h>

#define AF_BLUETOOTH 31
#define BTPROTO_L2CAP 0

struct sockaddr_l2 {
    unsigned short l2_family;
    unsigned short l2_psm;
    unsigned char l2_bdaddr[6];
    unsigned short l2_cid;
    unsigned char l2_bdaddr_type;
};

#define L2CAP_CID_ATT 4

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

int main(int argc, char *argv[])
{
    int sock;
    struct sockaddr_l2 addr;
    unsigned char bdaddr[6];

    if (argc < 2) {
        printf("Usage: %s <bdaddr>\n", argv[0]);
        return 1;
    }

    if (parse_bdaddr(argv[1], bdaddr) < 0) {
        fprintf(stderr, "Invalid address\n");
        return 1;
    }

    printf("Attempting L2CAP ATT connection to %s...\n", argv[1]);

    sock = socket(AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_L2CAP);
    if (sock < 0) {
        perror("socket");
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.l2_family = AF_BLUETOOTH;
    addr.l2_psm = 0; /* ATT */
    addr.l2_cid = L2CAP_CID_ATT;
    addr.l2_bdaddr_type = 0; /* Public */
    memcpy(addr.l2_bdaddr, bdaddr, 6);

    printf("Connecting...\n");
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        close(sock);
        return 1;
    }

    printf("Connected! Press Enter to disconnect...\n");
    getchar();

    close(sock);
    return 0;
}
