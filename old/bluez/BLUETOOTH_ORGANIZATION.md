# Bluetooth Implementation Organization

All Bluetooth-related files have been organized in `/mnt/us/bluetooth/` directory structure.

## Directory Structure

```
/mnt/us/bluetooth/
├── bin/                          # Executables and tools
│   ├── vhci_stpbt_bridge        # Custom MediaTek STP↔VHCI bridge
│   ├── ld-musl-armhf.so.1       # Musl libc loader (required for BlueZ binaries)
│   ├── hci_info                 # HCI device information tool
│   ├── hci_test                 # HCI socket testing tool
│   ├── hci_tool                 # General HCI utility
│   ├── bluetoothctl             # Interactive Bluetooth control (BlueZ)
│   ├── hciconfig                # HCI device configuration (BlueZ)
│   ├── hcitool                  # HCI tool for discovery/connections (BlueZ)
│   ├── btmon                    # Bluetooth monitor (BlueZ)
│   └── [... other BlueZ tools]
├── libs/                         # Shared libraries for BlueZ
│   ├── libbluetooth.so.*
│   └── [... other libraries]
├── libexec/bluetooth/            # BlueZ daemons
│   └── bluetoothd               # Main Bluetooth daemon
└── scripts/                      # Helper scripts
    └── start_bluez.sh           # Startup script for BlueZ stack
```

## Quick Start

```bash
/mnt/us/bluetooth/scripts/start_bluez.sh
```

## Files Removed (Obsolete/Failed)

The following files were identified as failed experiments and removed:

- `pair_agent` - Incomplete pairing agent (non-functional)
- `pair_device.sh` - Hardcoded pairing script (doesn't work due to SMP limitation)
- `bluez_tools.tar.gz` - Archive of already-extracted tools

## Files Kept (Working)

### Custom Tools
- **vhci_stpbt_bridge** - Core bridge between MediaTek `/dev/stpbt` and Linux `/dev/vhci`
- **hci_info** - Display HCI device information
- **hci_test** - Test HCI sockets and ioctls
- **hci_tool** - General HCI utility

### BlueZ 5.43
- Full BlueZ suite in `bin/` and `libexec/bluetooth/`
- Libraries in `libs/`
- Musl loader required for all BlueZ binaries

### Scripts
- **start_bluez.sh** - Automated startup script that:
  - Loads kernel modules (bluetooth, hci_uart, hci_vhci, wmt_cdev_bt)
  - Starts vhci_stpbt_bridge
  - Brings up hci0 interface
  - Starts bluetoothd daemon

## Usage

### Start Bluetooth

```bash
/mnt/us/bluetooth/scripts/start_bluez.sh
```

### Use bluetoothctl

```bash
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl
```

### Check HCI Status

```bash
/mnt/us/bluetooth/bin/hci_info
```

## Important Notes

1. **BLE HID Limitation**: BLE HID devices (keyboards, mice) will NOT pair due to kernel SMP initialization issue. See `BLE_SMP_LIMITATION.md` for full technical details.

2. **Path Updates**: All documentation has been updated to reflect the new `/mnt/us/bluetooth/` structure.

3. **Environment Variable**: All BlueZ tools require:
   ```bash
   export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
   ```

4. **Musl Loader**: BlueZ binaries are dynamically linked to musl libc and must be run through:
   ```bash
   /mnt/us/bluetooth/bin/ld-musl-armhf.so.1 <binary>
   ```

## Root Directory Cleanup

The `/mnt/us/` root directory has been cleaned of Bluetooth-related files. All Bluetooth implementation files are now properly organized in `/mnt/us/bluetooth/`.

## What Works

- Bluetooth device scanning and discovery
- Classic Bluetooth pairing and connections
- BLE scanning and basic connections
- Non-secure BLE operations
- HCI commands and operations

## What Doesn't Work

- BLE HID device pairing (keyboards, mice, game controllers)
- BLE operations requiring SMP security
- BLE device bonding

For technical details on limitations, see `BLE_SMP_LIMITATION.md`.
