# Kindle Bluetooth Development

This project enables standard Bluetooth functionality on the Kindle MT8110 Bellatrix (MediaTek MT8512), replacing Amazon's proprietary Bluetooth stack with BlueZ and adding BLE HID support via Google Bumble.

## Quick Start

**Connect BLE HID devices (keyboard, mouse, controller):**

```bash
# Start daemon for persistent connection
ssh kindle '/etc/init.d/ble-hid start'

# Check status
ssh kindle '/etc/init.d/ble-hid status'

# View logs
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

See `QUICK_START.md` for detailed usage instructions.

## What Works

- **BLE HID Devices** - Keyboards, mice, game controllers (via Bumble)
- **Classic Bluetooth** - Discovery, pairing, connections (via BlueZ)
- **BLE Scanning** - Device discovery and basic connections (via BlueZ)

## Current Implementation

### BLE HID Solution (Working)

**Technology:** Google Bumble - Userspace Bluetooth stack

**Architecture:**
```
MediaTek MT8512 → /dev/stpbt → Bumble (Python) → /dev/uhid → Linux Input
```

**Why Bumble:**
The Kindle's kernel (4.9.77-lab126) has a bug where SMP (Security Manager Protocol) is not properly initialized for virtual HCI devices. This prevents BLE HID pairing through the kernel Bluetooth stack. Bumble implements SMP entirely in userspace, bypassing the kernel limitation.

**Components:**
- Python 3.8 at `/mnt/us/python3.8-kindle/`
- Google Bumble 0.0.200 with cryptography library
- BLE HID implementation at `/mnt/us/bumble_ble_hid/`
- Init daemon at `/etc/init.d/ble-hid`

See `bumble_ble_hid/README.md` for technical details.

### Classic Bluetooth (Working)

**Technology:** BlueZ 5.43 + vhci_stpbt_bridge

**Architecture:**
```
MediaTek MT8512 → /dev/stpbt → vhci_stpbt_bridge → /dev/vhci → BlueZ
```

**Components:**
- BlueZ 5.43 deployed to `/mnt/us/bluetooth/` (musl-based)
- VHCI bridge: `vhci_stpbt_bridge_musl`
- Full BlueZ tools: bluetoothctl, btmon, etc.

**Usage:**
```bash
ssh root@192.168.0.65
/mnt/us/bluetooth/scripts/start_bluez.sh
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl
```

## Project Structure

```
kindle/
├── README.md                           - This file
├── QUICK_START.md                      - User guide
│
├── src/
│   ├── vhci_stpbt_bridge.c            - VHCI bridge (Classic BT)
│   ├── pty_stpbt_bridge.c             - PTY experiment (reference)
│   └── pty_stpbt_bridge_ldisc.c       - PTY with line discipline (reference)
│
├── bumble_ble_hid/                    - BLE HID solution
│   ├── README.md                      - Technical details
│   ├── USAGE_EXAMPLES.md              - Usage examples
│   ├── DAEMON_NOTES.md                - Daemon information
│   ├── kindle_ble_hid.py              - Main implementation
│   ├── ble_hid_daemon.py              - Persistent daemon
│   ├── kindle_ble_hid.sh              - Helper script
│   └── ble-hid-init.sh                - Init script
│
├── bluez_full/                        - BlueZ deployment (102 MB)
│   ├── bin/                           - BlueZ tools
│   ├── libexec/bluetooth/             - bluetoothd daemon
│   └── libs/                          - Shared libraries
│
├── vhci_stpbt_bridge_musl             - Working VHCI bridge binary
│
└── Documentation
    ├── BLE_SMP_LIMITATION.md          - Kernel SMP bug analysis
    ├── BLE_SMP_RESEARCH.md            - Solutions research
    ├── PTY_EXPERIMENT_SUMMARY_FINAL.md - PTY approach failure analysis
    ├── BUMBLE_BLE_HID_FIXES.md        - Bumble API compatibility fixes
    ├── BUMBLE_IMPLEMENTATION_SUMMARY.md - Implementation details
    ├── BLUETOOTH_ORGANIZATION.md      - Device file organization
    ├── DAEMON_INSTALLATION.md         - Daemon setup
    ├── kindle_system_info.md          - Hardware and system info
    └── kindle_kernel_config.txt       - Full kernel config
```

## Technical Details

### Hardware
- **Device:** Kindle MT8110 Bellatrix
- **SoC:** MediaTek MT8512 (ARMv7-A Cortex-A53)
- **Kernel:** Linux 4.9.77-lab126
- **Bluetooth:** MediaTek CONSYS via `/dev/stpbt`

### Build Information
```
Target: arm-linux-gnueabi (EABI5)
ABI: EABI5 (soft-float or softfp VFP)
Architecture: ARMv7-A (Cortex-A53)
Kernel: 4.9.77-lab126
glibc: 2.20 (on device)
musl: Used for BlueZ cross-compilation
```

### Cross-Compilation
```bash
# Uncomment in Makefile for ARM build:
# CC = arm-linux-gnueabihf-gcc
# CFLAGS += -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=softfp -mtune=cortex-a53
# LDFLAGS += -static

make
```

## Known Limitations

### Kernel SMP Bug
The kernel's virtual HCI implementation doesn't properly initialize SMP context (`conn->smp`), preventing BLE device pairing that requires encryption. This affects:
- BLE HID devices
- BLE bonding
- Any secure BLE operation

**Solution:** Bumble userspace stack bypasses kernel SMP entirely.

### Single BLE HID Device
The current daemon implementation supports only one BLE HID device at a time. See `bumble_ble_hid/DAEMON_NOTES.md` for details.

## Development History

This project went through several approaches:

1. **Classic Bluetooth via VHCI** - ✓ Working
   - Built vhci_stpbt_bridge to connect `/dev/stpbt` to BlueZ
   - Deployed full BlueZ 5.43 stack

2. **BLE via VHCI** - ✗ Failed (kernel SMP bug)
   - Discovered kernel doesn't initialize SMP for virtual HCI
   - Multiple direct connection attempts failed

3. **PTY + hci_uart approach** - ✗ Failed (hardware initialization)
   - Attempted to use hci_uart driver instead of VHCI
   - Successfully attached line discipline but no hci0 created
   - Hardware initialization requirements cannot be met with PTY

4. **Bumble userspace stack** - ✓ Working (final solution)
   - Implements full BLE stack including SMP in userspace
   - Bypasses kernel Bluetooth code entirely
   - Successfully pairs and operates BLE HID devices

All experimental code and detailed failure analysis preserved in git history under tag `pre-cleanup`.

## Device Connection

```bash
ssh root@192.168.0.65
```

## Author

Lucas Zampieri <lzampier@redhat.com>
