# Kindle Bluetooth Development

This project enables BLE HID support on the Kindle MT8110 Bellatrix (MediaTek MT8512) using Google Bumble, a userspace Bluetooth stack that bypasses kernel limitations.

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

- **BLE HID Devices** - Keyboards, mice, game controllers via Google Bumble userspace stack

## Implementation

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

## Project Structure

```
kindle/
├── README.md                  - This file
├── QUICK_START.md            - User guide
├── BLE_SMP_LIMITATION.md     - Technical explanation
├── kindle_system_info.md     - Hardware reference
│
└── bumble_ble_hid/           - BLE HID implementation
    ├── README.md             - Technical details
    ├── INSTALLATION.md       - Setup guide
    ├── USAGE_EXAMPLES.md     - Usage examples
    ├── DEBUG_UHID.md         - Debugging guide
    ├── kindle_ble_hid.py     - Main implementation
    ├── ble_hid_daemon.py     - Persistent daemon
    └── ble-hid-init.sh       - Init script
```

## Technical Details

### Hardware
- **Device:** Kindle MT8110 Bellatrix
- **SoC:** MediaTek MT8512 (ARMv7-A Cortex-A53)
- **Kernel:** Linux 4.9.77-lab126
- **Bluetooth:** MediaTek CONSYS via `/dev/stpbt`

### Software Stack
- Python 3.8 (cross-compiled for ARMv7-A)
- Google Bumble 0.0.200
- cryptography library 43.0.0

## Known Limitations

### Kernel SMP Bug
The kernel's virtual HCI implementation doesn't properly initialize SMP context (`conn->smp`), preventing BLE device pairing that requires encryption. This affects:
- BLE HID devices
- BLE bonding
- Any secure BLE operation

**Solution:** Bumble userspace stack bypasses kernel SMP entirely.

### Single BLE HID Device
The current daemon implementation supports only one BLE HID device at a time. See `bumble_ble_hid/DAEMON_NOTES.md` for details.

## Installation

See `bumble_ble_hid/INSTALLATION.md` for complete setup instructions on your Kindle device.
