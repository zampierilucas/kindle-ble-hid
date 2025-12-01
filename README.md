# Kindle Bluetooth Development

This directory contains development work for enabling standard BlueZ Bluetooth stack on Kindle (MT8110 Bellatrix with MediaTek MT8512).

## Documentation

### Main Documents
- **kindle_system_info.md** - Complete system information, Bluetooth setup instructions, and hardware details
- **BLE_SMP_LIMITATION.md** - Technical analysis of BLE HID pairing limitation (kernel SMP issue)
- **BLE_SMP_RESEARCH.md** - Deep research into solutions for the SMP limitation (Dec 2025)
- **BLUETOOTH_ORGANIZATION.md** - Organization of Bluetooth files on the Kindle device
- **kindle_kernel_config.txt** - Full kernel configuration extracted from device

### Quick Reference

**Start Bluetooth on Kindle:**
```bash
ssh root@192.168.0.65
/mnt/us/bluetooth/scripts/start_bluez.sh
```

**Use bluetoothctl:**
```bash
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl
```

## Active Binaries

These are the working binaries currently deployed on the Kindle:

- **vhci_stpbt_bridge_musl** - Main bridge between `/dev/stpbt` and `/dev/vhci` (musl version)
- **hci_info** - Display HCI device information
- **hci_test** - Test HCI sockets and operations
- **hci_tool** - General HCI utility

## Directory Structure

### src/
Source code for custom tools:
- `vhci_stpbt_bridge.c` - VHCI ↔ stpbt bridge implementation
- `hci_info.c` - HCI info tool source
- `hci_test.c` - HCI test tool source
- `hci_tool.c` - HCI utility source
- `ble_*.c`, `bt_*.c` - Failed experiment sources (kept for reference)

### bluez_full/
Complete BlueZ 5.43 cross-compiled installation including:
- bin/ - All BlueZ tools
- libexec/bluetooth/ - bluetoothd daemon
- libs/ - Shared libraries
- ld-musl-armhf.so.1 - Musl libc loader

This is what's deployed to `/mnt/us/bluetooth/` on the device.

### bluez_build/
BlueZ build directory (can be deleted if space needed)

### bluez_arm/
ARM cross-compilation artifacts (can be deleted if space needed)

### build_artifacts/
Archived failed experiments and old versions:
- Failed BLE/BT tool binaries
- Old startup scripts
- glibc version of vhci_stpbt_bridge
- Build scripts

## What Works

- ✅ Classic Bluetooth discovery and pairing
- ✅ BLE device scanning
- ✅ Basic BLE connections (non-secure)
- ✅ HCI commands and operations
- ✅ BlueZ 5.43 full functionality (except BLE HID)

## What Doesn't Work

- ❌ BLE HID device pairing (keyboards, mice, game controllers)
- ❌ Any BLE operation requiring SMP (Security Manager Protocol)
- ❌ BLE device bonding

**Root Cause:** Linux kernel 4.9.77-lab126 doesn't properly initialize SMP context for virtual HCI devices. See `BLE_SMP_LIMITATION.md` for full technical analysis.

## Build Information

### Cross-Compilation Target
```
Target: arm-linux-gnueabi (EABI5)
ABI: EABI5 (soft-float or softfp VFP)
Architecture: ARMv7-A (Cortex-A53)
Kernel: 4.9.77-lab126
glibc: 2.20
```

### GCC Flags Used
```bash
-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=softfp -mtune=cortex-a53
```

### Musl Build
BlueZ tools are built with musl libc for easier static linking and deployment.

## Device Connection

```bash
ssh root@192.168.0.65
```

## Project Timeline

1. Disabled Amazon's proprietary BT stack
2. Built and deployed BlueZ 5.43 with musl
3. Created vhci_stpbt_bridge for MediaTek STP protocol
4. Identified and documented BLE SMP limitation
5. Organized all files in `/mnt/us/bluetooth/`
6. **Implemented Google Bumble BLE HID solution** (Dec 2025)

## BLE HID Solution

The kernel SMP bug has been bypassed using Google Bumble, a userspace BLE stack.

**Status:** WORKING (fixed Dec 1, 2025)

**Location:** `bumble_ble_hid/`

**Quick Start:**

See `QUICK_START.md` for full guide.

**Persistent connection (daemon):**
```bash
# Start daemon for auto-reconnect
ssh kindle '/etc/init.d/ble-hid start'

# Check status
ssh kindle '/etc/init.d/ble-hid status'

# View logs
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

**One-time connection:**
```bash
# Scan and select device
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh

# Or connect to specific address
./kindle_ble_hid.sh AA:BB:CC:DD:EE:FF
```

**How it works:**
- Connects directly to `/dev/stpbt` using Bumble's file transport
- Handles SMP pairing in userspace (bypasses kernel bug)
- Discovers BLE HID services (HOGP)
- Injects input via Linux UHID
- Auto-reconnects on disconnection (daemon mode)

**Installed Components:**
- Python 3.8 at `/mnt/us/python3.8-kindle/`
- Google Bumble 0.0.200 library
- cryptography library with OpenSSL 3.x support
- Fixed `kindle_ble_hid.py` implementation
- `ble_hid_daemon.py` for persistent connections
- Init script at `/etc/init.d/ble-hid`

See `bumble_ble_hid/README.md` for detailed documentation, `QUICK_START.md` for usage guide, and `BUMBLE_BLE_HID_FIXES.md` for API fix details.

## Legacy Work

See `BLE_SMP_RESEARCH.md` for detailed research on the BLE HID pairing issue.

### Alternative Approaches Explored

1. **PTY + hci_uart:** TESTED - FAILED (Dec 1, 2025)
   - Successfully attached N_HCI line discipline
   - hci_uart driver did not create hci0 device
   - Requires hardware initialization not achievable with PTY
   - See `PTY_EXPERIMENT_RESULTS.md` for complete analysis
2. **USB Bluetooth dongle:** Hardware workaround if USB port available

## Author

Lucas Zampieri <lzampier@redhat.com>
