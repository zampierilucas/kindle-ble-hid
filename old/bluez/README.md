# BlueZ Implementation (Partial Success)

This directory contains the BlueZ-based Bluetooth implementation that worked for Classic Bluetooth but failed for BLE HID devices.

## What Worked

- Classic Bluetooth discovery and pairing
- BLE device scanning
- Basic BLE connections (non-secure)
- Full BlueZ 5.43 functionality

## What Didn't Work

- BLE HID device pairing (keyboards, mice, controllers)
- Any BLE operation requiring SMP (Security Manager Protocol)
- BLE device bonding

## Why It Failed

The Linux kernel 4.9.77-lab126 doesn't properly initialize SMP context for virtual HCI devices. The kernel's `conn->smp` structure remains NULL for LE connections, preventing any secure BLE operations.

## Components

### vhci_stpbt_bridge
- **Binary:** `vhci_stpbt_bridge_musl` (musl libc, static)
- **Source:** `../src/vhci_stpbt_bridge.c`
- **Purpose:** Bridges MediaTek's `/dev/stpbt` to Linux `/dev/vhci`
- **Protocol:** H4 HCI packet forwarding
- **Status:** Works perfectly for Classic BT

### BlueZ 5.43 Deployment
- **Location:** `bluez_full/` (102 MB)
- **Build:** Cross-compiled with musl libc for ARMv7-A
- **Deployed to:** `/mnt/us/bluetooth/` on Kindle
- **Includes:** Full BlueZ tools (bluetoothctl, btmon, etc.)

## Usage (If Needed)

```bash
ssh root@192.168.0.65
/mnt/us/bluetooth/scripts/start_bluez.sh
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl
```

## Why Google Bumble is Better

Bumble implements the entire Bluetooth stack (including SMP) in userspace, completely bypassing the kernel's Bluetooth code. This solves the SMP initialization bug and enables full BLE HID functionality.

## Documentation

For detailed technical analysis:
- `../../BLE_SMP_LIMITATION.md` - Kernel SMP bug explanation
- `../../BLE_SMP_RESEARCH.md` - Research into solutions
