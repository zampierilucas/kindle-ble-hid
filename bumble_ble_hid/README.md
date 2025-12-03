# Kindle BLE HID Host using Google Bumble

BLE HID device support for Kindle MT8512, bypassing the kernel SMP bug that prevents BLE HID pairing.

## Problem

The Kindle's kernel (4.9.77-lab126) has a bug where SMP (Security Manager Protocol) is not properly initialized for virtual HCI devices, preventing BLE HID devices from pairing.

## Solution

Google Bumble is a full Bluetooth stack in Python that includes complete SMP implementation, allowing us to bypass the kernel bug entirely.

## Architecture

```
MediaTek MT8512 → /dev/stpbt → Bumble Stack → /dev/uhid → Linux Input
                                    |
                                    +---> Multiple devices in parallel
                                    +---> Auto-reconnection
                                    +---> Pure HID pass-through
```

## Requirements

- Python 3.8 (installed at `/mnt/us/python3.8-kindle/`)
- Google Bumble 0.0.200 library
- Root access

## Quick Start

### Scan and Connect
```bash
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh
```

### Connect to Specific Device
```bash
./kindle_ble_hid.sh AA:BB:CC:DD:EE:FF
```

### Persistent Daemon

Start daemon for auto-reconnecting connections:
```bash
/etc/init.d/ble-hid start
```

Configure devices in `/mnt/us/bumble_ble_hid/devices.conf`:
```
# One device address per line
AA:BB:CC:DD:EE:FF
11:22:33:44:55:66
```

Monitor logs:
```bash
tail -f /var/log/ble_hid_daemon.log
```

## Features

### Multi-Device Support
- Connect to multiple BLE HID devices simultaneously
- Each device gets its own Bumble host instance
- Independent reconnection logic per device

### Smart Reconnection
- **Active mode** (user input detected): 3 second retry
- **Idle mode** (no input for 60s): 30 second retry
- Connection timeout: 10 seconds

### Pure Pass-Through with Permissive Mode (Default)
- **Permissive vendor-specific HID descriptor** - accepts any report format without validation
- HID reports forwarded unchanged to UHID
- Works with any BLE HID device: keyboards, mice, gamepads, remotes, etc.
- Handles broken devices with mismatched Report IDs (like cheap Chinese remotes)
- No Report ID validation or device-specific mapping

### HID Descriptor Modes

The implementation **automatically detects** device type (mouse/keyboard) from the HID Information characteristic and selects the appropriate standard USB HID descriptor. No configuration needed!

```bash
# Auto-detection (default) - reads device type and picks standard descriptor
./kindle_ble_hid.sh
```

You can override auto-detection with environment variables:

```bash
# Force standard USB HID mouse descriptor (3-byte report: buttons, x, y)
export KINDLE_BLE_HID_DESCRIPTOR_MODE=standard_mouse
./kindle_ble_hid.sh

# Force standard USB HID keyboard descriptor (8-byte report: modifiers + keys)
export KINDLE_BLE_HID_DESCRIPTOR_MODE=standard_keyboard
./kindle_ble_hid.sh

# Use device's original descriptor (may fail with broken devices)
export KINDLE_BLE_HID_DESCRIPTOR_MODE=original
./kindle_ble_hid.sh

# Use permissive 16-report-ID descriptor (for unrecognized device types)
export KINDLE_BLE_HID_DESCRIPTOR_MODE=permissive
./kindle_ble_hid.sh
```

**How it works**: The code reads the HID Information characteristic's Flags byte to detect device type (0x01=keyboard, 0x02=mouse), then automatically selects the appropriate standard USB HID descriptor based on USB HID 1.11 specification (proven working in btferret).

## Files

| File | Purpose |
|------|---------|
| `kindle_ble_hid.py` | Main BLE HID implementation |
| `kindle_ble_hid.sh` | Interactive scanning/connection |
| `ble_hid_daemon.py` | Persistent connection daemon |
| `devices.conf` | Device addresses for daemon |
| `/etc/init.d/ble-hid` | Init script |

## Troubleshooting

### Permission denied for /dev/stpbt
```bash
chmod 666 /dev/stpbt
```

### Permission denied for /dev/uhid
```bash
chmod 666 /dev/uhid
```

### "Resource busy: '/dev/stpbt'"
```bash
killall ble_hid_daemon.py kindle_ble_hid.py
/etc/init.d/ble-hid stop
sleep 2
/etc/init.d/ble-hid start
```

### No HID devices found
- Ensure device is in pairing mode
- Check device advertises HID service UUID (0x1812)
- Try increasing scan duration

## Limitations

1. Requires Python 3.8 runtime
2. Runs independently of BlueZ
3. Continuous BLE connection impacts battery life

## References

- [Google Bumble](https://github.com/google/bumble)
- [BLE HID Service Specification](https://www.bluetooth.com/specifications/specs/hid-service-1-0/)
- [Linux UHID Documentation](https://www.kernel.org/doc/html/latest/hid/uhid.html)

## Author

Lucas Zampieri <lzampier@redhat.com>
