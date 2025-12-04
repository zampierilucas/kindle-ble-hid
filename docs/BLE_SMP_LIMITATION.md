# BLE HID Pairing on Kindle - RESOLVED

## Problem Statement (Historical)

BLE HID devices (keyboards, mice, etc.) could not be paired through a BlueZ + vhci_stpbt_bridge setup due to a kernel-level SMP (Security Manager Protocol) initialization issue.

## Solution

This issue has been **RESOLVED** by using Google Bumble instead of the kernel's Bluetooth stack. Bumble is a complete Bluetooth stack implemented in Python that includes full SMP support and bypasses the kernel bug entirely.

**Current working implementation:** `/mnt/us/bumble_ble_hid/` with pure UHID pass-through mode supporting multiple simultaneous BLE HID devices.

See `bumble_ble_hid/README.md` for usage instructions.

---

## Historical Technical Details (For Reference)

The following sections document the original kernel bug and why the BlueZ approach failed. This is kept for reference, but the issue no longer affects the current Bumble-based implementation.

## Technical Background

### Original Architecture (BlueZ Approach - Failed)

The failed BlueZ approach used:
1. **MediaTek MT8512 CONSYS** - Proprietary connectivity subsystem
2. **STP Layer** - Serial Transport Protocol multiplexing WiFi/BT/GPS
3. **/dev/stpbt** - Character device exposing BT data via STP
4. **vhci_stpbt_bridge** - Userspace bridge forwarding HCI packets between `/dev/vhci` and `/dev/stpbt`
5. **BlueZ 5.43** - Standard Linux Bluetooth stack running on virtual HCI (hci0)

### Current Architecture (Bumble Approach - Working)

The working Bumble approach uses:
1. **MediaTek MT8512 CONSYS** - Same proprietary connectivity subsystem
2. **STP Layer** - Same Serial Transport Protocol
3. **/dev/stpbt** - Same character device
4. **Bumble File Transport** - Reads/writes H4 HCI packets directly from `/dev/stpbt`
5. **Bumble Host Stack** - Complete Python Bluetooth stack with full SMP implementation
6. **/dev/uhid** - Linux UHID interface for virtual HID device creation

### BLE Security Requirements

BLE device pairing requires:
- **L2CAP Fixed Channel 0x0006** - SMP channel for security operations
- **Kernel SMP Context** - `conn->smp` structure initialized for each connection
- **Security Manager Protocol** - Handles pairing, encryption key exchange, bonding

### What Works

- BLE device discovery and scanning
- Basic BLE connection establishment
- Non-secure BLE operations
- Classic Bluetooth (non-LE) operations

### What Doesn't Work

- BLE HID device pairing (keyboards, mice)
- Any BLE operation requiring security/encryption
- Bonding with BLE devices

## Root Cause Analysis

### The Error

```
Bluetooth: SMP security requested but not available
```

This error appears repeatedly in `dmesg` when attempting to pair BLE devices.

### Why It Happens

The kernel's SMP implementation checks for a valid SMP context (`conn->smp`) when security is requested. For virtual HCI devices created through `/dev/vhci`, this context is not properly initialized.

**Kernel Code Path:**
1. BlueZ requests pairing via L2CAP SMP channel (CID 0x0006)
2. Kernel function `smp_conn_security()` is called
3. It checks `if (!chan)` where `chan = conn->smp`
4. For vhci connections, `conn->smp` is NULL
5. Error printed: "SMP security requested but not available"

### Known Kernel Bug

This issue is related to a known kernel timing bug that was fixed in commit **d8949aad3eab5d396f4fefcd581773bf07b9a79e** for kernels 4.0+.

However, Amazon's kernel **4.9.77-lab126** appears to either:
- Not have this patch applied (custom backport)
- Have a different issue with virtual HCI SMP initialization

### Research Sources

- [BlueZ Issue #581](https://github.com/bluez/bluez/issues/581) - SMP security error discussion
- [Raspberry Pi Stack Exchange](https://raspberrypi.stackexchange.com/questions/36552/pairing-the-pi-over-bt-4-0-le-to-a-ms-universal-foldable-keyboard-fails) - BLE keyboard pairing
- [Red Hat Bugzilla #1259074](https://bugzilla.redhat.com/show_bug.cgi?id=1259074) - Bluetooth keyboard connection failures
- [Linux Bluetooth Mailing List](https://www.spinics.net/lists/linux-bluetooth/msg64139.html) - SMP security discussion
- [Arch Linux Bug #46006](https://bugs.archlinux.org/task/46006) - Bluetooth SMP bug
- [Debian Bug #819598](https://bugs.debian.org/819598) - BLE HID device issues
- [Linux Kernel Commit d8949aa](https://github.com/torvalds/linux/commit/d8949aad3eab5d396f4fefcd581773bf07b9a79e) - SMP timing fix

## Attempted Solutions

### 1. Direct UART HCI Mode ❌ NOT FEASIBLE

**Approach:** Bypass STP layer and attach BT hardware directly via UART HCI

**Finding:** MediaTek MT8512 uses proprietary CONSYS architecture where:
- BT is not exposed as a standard UART device
- Firmware is integrated and loaded through WMT driver
- No MediaTek BT firmware files available (`/lib/firmware` empty)
- No `btmtkuart` kernel driver compiled
- Device tree shows only `mediatek,mt8512-consys` subsystem
- STP layer is mandatory for this chip architecture

**Conclusion:** Hardware architecture doesn't support direct UART HCI mode.

### 2. Amazon BT Stack ❌ REJECTED

**Approach:** Use Amazon's ACE (Amazon Common Executive) BT stack

**Reason for Rejection:** Amazon's stack only supports Amazon-authorized devices and products. Not suitable for general BLE device pairing.

### 3. Userspace BLE Tools ❌ FAILED

**Approach:** Use pre-existing `ble_pair_simple`, `ble_connect` tools

**Finding:** These tools were incomplete experiments that don't work:
- Return "Invalid argument" error
- Appear to be abandoned development attempts
- Have been removed from `/mnt/us/`

### 4. Kernel SMP Patch ⚠️ REQUIRES KERNEL REBUILD

**Approach:** Apply kernel patch d8949aad3eab5d396f4fefcd581773bf07b9a79e

**Challenge:** Would require:
- Amazon kernel source code (4.9.77-lab126)
- Cross-compilation toolchain
- Kernel rebuild and installation
- Boot process modification to load custom kernel
- Risk of bricking device

**Status:** Not attempted due to complexity and risk.

## Attempted Solutions (Historical)

### Chosen Solution: Userspace Bumble Stack ✅ WORKING

**Approach:** Use Google Bumble - a complete Bluetooth stack in Python

**Implementation:**
- Bumble reads/writes H4 HCI packets directly from `/dev/stpbt`
- Complete SMP implementation in userspace (pairing, bonding, encryption)
- GATT client for HID service discovery and report handling
- UHID integration for virtual HID device creation
- Pure pass-through mode with minimal latency

**Status:** Fully functional - supports multiple simultaneous BLE HID devices

**Benefits:**
- No kernel modifications required
- Complete control over Bluetooth stack
- Bypasses kernel SMP bug entirely
- Supports advanced features (multi-device, report buffering)
- Easy to debug and extend

### Rejected Solutions

#### Option A: Kernel Module for SMP Context Initialization ❌

**Difficulty:** High - requires deep kernel Bluetooth stack knowledge
**Risk:** Moderate - kernel module bugs can cause system instability
**Rejection Reason:** Unnecessary with Bumble solution

#### Option B: Custom Kernel Build ❌

**Difficulty:** Very High - requires kernel source and toolchain
**Risk:** High - custom kernel may break system boot
**Rejection Reason:** Too risky, Bumble provides better solution

#### Option C: BlueZ with Kernel Patches ❌

**Difficulty:** Very High - requires kernel rebuild
**Risk:** High - may brick device
**Rejection Reason:** Bumble works without kernel modifications

## Current System State

### Working Components ✅

- MediaTek WMT/STP drivers loaded
- `/dev/stpbt` character device functional
- **Bumble Bluetooth stack** reading/writing HCI packets directly
- **BLE HID pairing and bonding** - WORKING
- **BLE HID device support** - WORKING (keyboards, mice, game controllers)
- **BLE security/encryption** - WORKING (full SMP implementation)
- **Multi-device support** - Multiple simultaneous BLE HID connections
- **UHID integration** - Virtual HID devices appear as standard input devices

### Legacy Components (Not Used)

- `vhci_stpbt_bridge` - Old bridge binary (no longer needed)
- `start_bluez.sh` - BlueZ startup script (deprecated)
- BlueZ 5.43 binaries - Not used in current implementation
- `hci_info`, `hci_test`, `hci_tool` - Diagnostic tools (optional)

### Current Implementation Files

Working implementation in `/mnt/us/bumble_ble_hid/`:
- `kindle_ble_hid.py` - Main BLE HID daemon with Bumble
- `ble_hid_daemon.py` - Pure UHID pass-through daemon
- `device_config.json` - Bumble device configuration
- `start_ble_hid.sh` - Startup script
- `requirements.txt` - Python dependencies

## Conclusion

The BLE HID pairing issue has been **RESOLVED** by using Google Bumble instead of the kernel's Bluetooth stack. Bumble implements the complete Bluetooth specification in userspace, including full SMP support, which bypasses the kernel bug entirely.

**Key advantages of the Bumble approach:**
- No kernel modifications required
- Complete SMP implementation (pairing, bonding, encryption)
- Multi-device support
- Pure UHID pass-through mode with minimal latency
- Easy to debug and extend
- Works on stock Kindle firmware

The implementation is fully functional and supports all BLE HID device types including keyboards, mice, and game controllers with multiple simultaneous connections.
