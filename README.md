> **This project has been superseded by [kindle-hid-passthrough](https://github.com/zampierilucas/kindle-hid-passthrough)**, which provides a cleaner UHID pass-through implementation with better performance and simpler architecture.

---

# Kindle BLE HID Support

Connect BLE keyboards, mice, and game controllers to your Kindle using Google Bumble.

## Quick Start

```bash
# Start daemon
ssh kindle '/etc/init.d/ble-hid start'

# Check status
ssh kindle '/etc/init.d/ble-hid status'

# View logs
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

See `QUICK_START.md` for detailed usage.

## How It Works

```
MediaTek MT8512 → /dev/stpbt → Bumble (Python) → /dev/uhid → Linux Input
```

The Kindle's kernel has a bug preventing BLE HID pairing through the standard Linux Bluetooth stack. Bumble implements the entire Bluetooth stack in Python, bypassing this limitation.

See `docs/BLE_SMP_LIMITATION.md` for technical details.

## Components

- Python 3.8 at `/mnt/us/python3.8-kindle/`
- Google Bumble 0.0.200
- BLE HID implementation in `bumble_ble_hid/`
- Init script at `/etc/init.d/ble-hid`

## Hardware

- **Device:** Kindle MT8110 Bellatrix
- **SoC:** MediaTek MT8512 (ARMv7-A Cortex-A53)
- **Kernel:** Linux 4.9.77-lab126
- **Bluetooth:** MediaTek CONSYS via `/dev/stpbt`

See `kindle_system_info.md` for complete system details.

## Features

- Multiple BLE HID devices simultaneously
- Auto-reconnection with activity-aware delays
- Pure UHID pass-through mode
- GATT characteristic caching for fast reconnection

## Project Structure

```
kindle/
├── README.md                   # This file
├── QUICK_START.md              # User guide
├── justfile                    # Deployment and management recipes
├── kindle_system_info.md       # Hardware reference
│
├── bumble_ble_hid/             # BLE HID implementation
│   ├── README.md               # Implementation details
│   ├── USAGE.md                # Usage guide
│   ├── SCRIPT_MODE_README.md   # Button script configuration
│   ├── kindle_ble_hid.py       # Main implementation
│   ├── ble_hid_daemon.py       # Persistent daemon
│   ├── button_config.json      # Button-to-script mapping
│   ├── devices.conf.example    # Device addresses config
│   ├── config.ini              # Configuration file
│   ├── ble-hid.init            # Init script template
│   └── Scripts/                # Shell scripts for button actions
│       ├── brightnessUp.sh
│       ├── brightnessDown.sh
│       ├── nextPage.sh
│       └── prevPage.sh
│
│
├── docs/
│   └── BLE_SMP_LIMITATION.md   # Technical background
│
└── tests/                      # Test suite
    ├── unit/                   # Unit tests
    │   ├── test_logic_only.py
    │   └── test_pure_passthrough.py
    └── Dockerfile              # Test environment
```
