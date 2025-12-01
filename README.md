# Kindle BLE HID Support

Connect BLE keyboards, mice, and game controllers to your Kindle MT8110 Bellatrix using Google Bumble.

## Quick Start

```bash
# Start daemon
ssh kindle '/etc/init.d/ble-hid start'

# Check status
ssh kindle '/etc/init.d/ble-hid status'

# View logs
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

**Note:** The `kindle` SSH host is already configured in `~/.ssh/config` and should be used instead of the IP address directly.

See `QUICK_START.md` for detailed usage and troubleshooting.

## How It Works

```
MediaTek MT8512 → /dev/stpbt → Bumble (Python) → /dev/uhid → Linux Input
```

**Why Google Bumble?**

The Kindle's kernel has a bug preventing BLE HID pairing through the standard Linux Bluetooth stack. Bumble implements the entire Bluetooth stack (including security/pairing) in userspace Python, bypassing this kernel limitation entirely.

See `BLE_SMP_LIMITATION.md` for technical details.

## Components

- Python 3.8 at `/mnt/us/python3.8-kindle/`
- Google Bumble 0.0.200
- BLE HID daemon at `/mnt/us/bumble_ble_hid/`
- Init script at `/etc/init.d/ble-hid`

## Hardware

- **Device:** Kindle MT8110 Bellatrix
- **SoC:** MediaTek MT8512 (ARMv7-A Cortex-A53)
- **Kernel:** Linux 4.9.77-lab126
- **Bluetooth:** MediaTek CONSYS via `/dev/stpbt`

## Limitations

- **Single device**: Daemon supports one BLE HID device at a time
- **Python runtime**: Requires Python 3.8 on device

See `bumble_ble_hid/DAEMON_NOTES.md` for details.

## Installation

See `bumble_ble_hid/INSTALLATION.md` for setup instructions.

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
    └── DEBUG_UHID.md         - Debugging guide
```
