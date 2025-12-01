# BLE SMP Research: Solving the HID Pairing Limitation

**Date:** December 1, 2025
**Author:** Lucas Zampieri <lzampier@redhat.com>

## Executive Summary

This document captures research into solving the BLE HID pairing limitation on the Kindle MT8512. The current `vhci_stpbt_bridge` implementation works correctly, but BLE HID devices cannot pair due to a kernel-level SMP (Security Manager Protocol) initialization bug affecting virtual HCI devices.

---

## Current Implementation Analysis

### vhci_stpbt_bridge Architecture

```
MediaTek MT8512 CONSYS
        |
        v
  /dev/stpbt (misc char device, major 192)
        |
        v
  vhci_stpbt_bridge (userspace H4 packet proxy)
        |
        v
  /dev/vhci (virtual HCI interface)
        |
        v
  Linux Bluetooth Subsystem (BlueZ)
        |
        v
  hci0 (virtual adapter)
```

### What the Bridge Does

The `vhci_stpbt_bridge.c` implementation:
1. Opens `/dev/vhci` - creates virtual HCI device (hci0)
2. Opens `/dev/stpbt` - MediaTek STP Bluetooth data channel
3. Parses H4 protocol packets (type byte + HCI payload)
4. Filters VHCI-internal vendor packets (0xff type)
5. Bidirectionally proxies HCI packets between interfaces

**Assessment:** The bridge implementation is correct and clean. The problem lies elsewhere.

### Why VHCI Was Chosen

`/dev/stpbt` is a **misc character device** (not a TTY):
```
crw-rw----  1 root bluetoot 192, 0 /dev/stpbt
```

The `hci_uart` driver requires TTY devices with line discipline support. Since `/dev/stpbt` lacks TTY infrastructure, VHCI was the logical choice for creating an HCI interface from a raw character device.

---

## Root Cause: Kernel SMP Bug

### The Error

When attempting BLE pairing, dmesg shows:
```
Bluetooth: SMP security requested but not available
```

### Kernel Code Analysis

From `net/bluetooth/smp.c` (kernel 4.9):

```c
int smp_conn_security(struct hci_conn *hcon, __u8 sec_level)
{
    struct l2cap_conn *conn = hcon->l2cap_data;
    struct l2cap_chan *chan;

    // ... security level checks ...

    chan = conn->smp;
    if (!chan) {
        BT_ERR("SMP security requested but not available");
        return 1;
    }
    // ... rest of function
}
```

### Why conn->smp is NULL

The SMP channel is registered via `smp_register()` when the HCI device powers on:

1. `smp_register()` checks if controller supports LE
2. Creates L2CAP fixed channel on CID 0x0006 (SMP)
3. Registers channel callbacks

**The timing issue:** For VHCI devices, there's a race condition where:
- SMP registration happens before device features are fully populated
- The kernel doesn't re-initialize SMP when LE features become available later
- Result: `conn->smp` remains NULL for LE connections

### Related Kernel Fixes

Several patches have addressed SMP timing issues:
- Commit `d8949aad3eab` - SMP timing fix (kernel 4.0+)
- Commit `cb28c306b93b` - SMP crash in unpairing fix
- Various fixes for `HCI_CONN_LE_SMP_PEND` flag handling

Kernel 4.9.77-lab126 appears to be missing some of these fixes or has a variant of the issue specific to VHCI.

### Key Insight

The VHCI driver (`hci_vhci.c`) sets:
```c
hdev->bus = HCI_VIRTUAL;  // bus type 0
```

Virtual devices may receive different treatment in the SMP initialization path compared to real hardware (USB, UART, SDIO).

---

## Alternative Approaches Evaluated

### Option 1: Pseudo-TTY + hci_uart

**Concept:** Wrap `/dev/stpbt` in a pseudo-TTY to use `hci_uart` driver

```
/dev/stpbt <-> [bridge] <-> pty master | pty slave <-> hci_uart ldisc
```

**Implementation:**
```c
int master = posix_openpt(O_RDWR);
grantpt(master);
unlockpt(master);
char *slave = ptsname(master);
// Bridge stpbt <-> master
// ldattach -d 15 <slave>  (15 = N_HCI)
```

**Verdict:** Worth testing. Low effort, may use different kernel code path.

**Risk:** SMP issue may be in bluetooth core, not VHCI-specific.

### Option 2: Google Bumble (Userspace BLE Stack)

**Source:** https://github.com/google/bumble

**What it is:** Full Bluetooth stack in Python including:
- Complete SMP implementation (pairing, bonding, encryption)
- L2CAP, ATT, GATT, GAP protocols
- Support for VHCI and custom transports

**Architecture:**
```
/dev/stpbt <-> Bumble Transport Adapter <-> Bumble Stack
                                                |
                                           SMP (userspace)
                                                |
                                           HOGP parsing
                                                |
                                           /dev/uhid <-> Linux Input
```

**Verdict:** Most promising solution. Completely bypasses kernel SMP.

**Pros:**
- Full control over BLE stack
- Active development, good documentation
- Python - easier development than C
- Can implement any BLE profile

**Cons:**
- Different stack than BlueZ
- Need Python runtime on Kindle
- Must implement HID over GATT parsing

### Option 3: btmtkuart/btmtksdio Driver

**Evaluated drivers:**
- `btmtkuart.c` - UART-based MediaTek BT
- `btmtksdio.c` - SDIO-based MediaTek BT

**Supported chips:**
| Chip | Interface | Compatible String |
|------|-----------|-------------------|
| MT7663 | SDIO | SDIO ID 0x7663 |
| MT7668 | SDIO | SDIO ID 0x7668 |
| MT7921 | SDIO | SDIO ID 0x7961 |
| MT7663U | UART | "mediatek,mt7663u-bluetooth" |
| MT7668U | UART | "mediatek,mt7668u-bluetooth" |

**Verdict:** NOT applicable. MT8512 uses CONSYS/STP architecture, not supported by these drivers.

### Option 4: Custom Kernel Driver

**Concept:** Write a proper HCI driver that interfaces with `/dev/stpbt` from kernel space.

**Verdict:** Very high effort, moderate risk. Would face same SMP issue unless kernel is also patched.

### Option 5: Kernel SMP Patch

**Concept:** Patch `net/bluetooth/smp.c` to fix the timing issue for VHCI.

**Challenges:**
- Need Amazon kernel source (may not be available for MT8512)
- Custom kernel build risks bricking device
- Must identify exact missing patches

**Verdict:** High risk, requires kernel expertise.

### Option 6: External USB Bluetooth Dongle

**Concept:** Use a USB BT adapter with proper kernel driver support.

**Verdict:** Simple workaround if USB port available. Bypasses all MT8512 issues.

---

## Kernel Configuration Finding

The Kindle's original kernel config shows:
```
# CONFIG_BT is not set
```

However, Bluetooth modules ARE loaded (from external .ko files):
```
bluetooth 378540 6 hci_vhci,hci_uart,btintel,btqca,btbcm
hci_vhci 2817 1
hci_uart 56512 0  <-- Not being used!
```

**Notable:** `hci_uart` is loaded but has 0 references - not actively used.

Available Bluetooth modules in `/lib/modules/4.9.77-lab126/kernel/drivers/bluetooth/`:
- bluetooth.ko (core)
- hci_uart.ko
- hci_vhci.ko
- btusb.ko, btbcm.ko, btintel.ko, btqca.ko, btrtl.ko
- btsdio.ko, btmrvl.ko, btmrvl_sdio.ko

---

## Hardware Architecture

### MediaTek MT8512 CONSYS

The MT8512 uses MediaTek's CONSYS (Connectivity Subsystem) architecture:

```
MT8512 SoC
    |
    +-- CONSYS (combo WiFi/BT/GPS/FM)
           |
           +-- WMT Driver (Wireless Management Task)
           |      |
           |      +-- wmt_drv.ko (core)
           |      +-- wmt_cdev_bt.ko (BT char device)
           |      +-- wmt_chrdev_wifi.ko
           |
           +-- STP Layer (Serial Transport Protocol)
                  |
                  +-- /dev/stpbt (BT data)
                  +-- /dev/stpwmt (WMT control)
```

**Key points:**
- BT is NOT exposed as standard UART
- STP multiplexes multiple wireless functions
- /dev/stpbt uses H4 HCI protocol
- No mainline kernel driver for MT8512 BT

---

## Comparison Summary

| Approach | Fixes SMP? | Effort | Risk | Status | Recommended |
|----------|-----------|--------|------|--------|-------------|
| Current (VHCI) | No | Done | Low | Working | Baseline |
| PTY + hci_uart | No | Low | Low | **FAILED** | Tested - not viable |
| Google Bumble | Yes | Medium | Low | Pending | **Primary solution** |
| btmtkuart | N/A | N/A | N/A | N/A | Not applicable |
| Kernel driver | Maybe | Very High | Medium | N/A | Not recommended |
| Kernel patch | Yes | High | High | N/A | Last resort |
| USB dongle | Yes | Low | None | N/A | Hardware workaround |

---

## Recommended Path Forward

### Phase 1: Quick Experiment (PTY + hci_uart) - COMPLETED

**Status:** Experiment completed December 1, 2025 - FAILED

Test whether using hci_uart via pseudo-TTY helps:

```bash
# Implemented: pty_stpbt_bridge_ldisc.c
# - Creates PTY master/slave pair
# - Attaches N_HCI line discipline via ioctl(TIOCSETD)
# - Bridges /dev/stpbt data through PTY
```

**Results:**
- ✓ PTY creation successful
- ✓ `/dev/stpbt` opened successfully
- ✓ N_HCI line discipline attached successfully
- ✗ **hci0 device NOT created**
- ✗ No data flow between stpbt and PTY
- ✗ Did not resolve SMP issue

**Failure Analysis:**

The hci_uart driver attached the line discipline but did not create an hci0 device. Root causes:

1. **Initialization Handshake Missing**: hci_uart expects hardware initialization sequences before registering HCI device
2. **MediaTek-Specific Requirements**: MT8512 hardware needs vendor-specific setup (WMT, firmware upload) that VHCI bypasses
3. **Chicken-and-Egg Problem**:
   - hci_uart won't create hci0 without initialization packets
   - `/dev/stpbt` won't send packets without commands
   - Can't send commands without hci0

**Key Finding:** VHCI is special - it creates hci0 immediately upon opening `/dev/vhci` with no hardware expectations. The hci_uart driver is hardware-oriented and requires proper UART initialization that our PTY cannot provide.

**Conclusion:** PTY + hci_uart approach is not viable for this hardware. The experiment confirmed that kernel-level workarounds cannot bypass the MediaTek-specific initialization requirements.

**Documentation:** See `PTY_EXPERIMENT_RESULTS.md` for complete technical analysis.

**Implementation Files:**
- `src/pty_stpbt_bridge.c` - Simple PTY bridge (no line discipline)
- `src/pty_stpbt_bridge_ldisc.c` - PTY bridge with N_HCI line discipline attachment
- `pty_stpbt_bridge_musl` - ARM static binary (248.2 KB)
- `build_arm_musl.sh` - Docker-based ARM cross-compilation script
- `PTY_EXPERIMENT.md` - Detailed testing procedures
- `PTY_EXPERIMENT_SUMMARY.md` - Quick reference guide
- `KINDLE_DEPLOYMENT.md` - Deployment instructions
- `kindle_test_simple.sh` - Automated test script

**Technical Achievements:**
- Successfully implemented `ioctl(TIOCSETD)` line discipline attachment
- Fixed O_NONBLOCK bug when opening `/dev/stpbt`
- Created working PTY bridge infrastructure
- Cross-compiled for ARM using Docker Alpine musl

### Phase 2: Google Bumble Implementation - RECOMMENDED

**Status:** Phase 1 has failed. This is now the recommended solution.

1. **Transport Layer**
   - Write Python class extending Bumble's Transport
   - Open /dev/stpbt, implement read/write methods
   - Handle H4 packet framing

2. **Device Setup**
   - Create Bumble Device with transport
   - Configure as LE peripheral/central
   - Enable SMP with appropriate IO capabilities

3. **HID Support**
   - Connect to BLE HID device
   - Discover GATT services (HID Service UUID: 0x1812)
   - Subscribe to Report characteristics
   - Parse HID reports

4. **Input Injection**
   - Open /dev/uhid
   - Create virtual HID device
   - Forward parsed HID reports

### Phase 3: Documentation and Cleanup

- Document final solution
- Create startup scripts
- Test with multiple HID devices

---

## References

### Kernel Sources
- hci_vhci.c: https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_vhci.c
- smp.c: https://github.com/torvalds/linux/blob/v4.9/net/bluetooth/smp.c
- hci_ldisc.c: https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_ldisc.c

### Related Bug Reports
- BlueZ Issue #581: SMP security error discussion
- Red Hat Bugzilla #1259074: Bluetooth keyboard connection failures
- Arch Linux Bug #46006: Bluetooth SMP bug

### MediaTek Documentation
- btmtkuart: https://cateee.net/lkddb/web-lkddb/BT_MTKUART.html
- btmtksdio: https://github.com/torvalds/linux/blob/master/drivers/bluetooth/btmtksdio.c

### Google Bumble
- Repository: https://github.com/google/bumble
- Documentation: https://google.github.io/bumble/
- PyPI: https://pypi.org/project/bumble/

### Stack Overflow / Forums
- VHCI SMP discussion: https://stackoverflow.com/questions/61532492/
- hciattach usage: https://stackoverflow.com/questions/41944822/
- NVIDIA forum thread: https://forums.developer.nvidia.com/t/bluetooth-smp-security-requested-but-not-available/56915

---

## Implementation Status

**IMPLEMENTED:** See `bumble_ble_hid/` directory for the Google Bumble-based solution.

The implementation includes:
- Direct `/dev/stpbt` transport using Bumble's file transport
- Full SMP pairing support (bypasses kernel bug)
- BLE HID service (HOGP) discovery and subscription
- UHID integration for Linux input injection

To use:
```bash
cd bumble_ble_hid
./start_ble_hid.sh
```

---

## Conclusion

The `vhci_stpbt_bridge` implementation is correct and was a reasonable architectural choice. The BLE HID limitation stems from a kernel SMP initialization bug affecting virtual HCI devices, not from the bridge design.

The most viable solution is implementing a userspace BLE stack using Google Bumble, which provides complete SMP implementation and bypasses the kernel bug entirely. This approach requires medium effort but offers low risk and full control over the Bluetooth stack.

**Update (Dec 2025):** The Bumble-based solution has been implemented in `bumble_ble_hid/`.
