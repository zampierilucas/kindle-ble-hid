# Kindle BLE HID Host using Google Bumble

This implementation provides BLE HID device support for the Kindle MT8512, bypassing the kernel SMP bug that prevents BLE HID pairing with the VHCI approach.

## Problem Statement

The Kindle's kernel (4.9.77-lab126) has a bug where SMP (Security Manager Protocol) is not properly initialized for virtual HCI devices. This prevents BLE HID devices (keyboards, mice, game controllers) from pairing because they require encrypted connections.

## Solution

Google Bumble is a full Bluetooth stack implemented in Python that includes:
- Complete SMP implementation (pairing, bonding, encryption)
- L2CAP, ATT, GATT protocols
- Support for various HCI transports including raw file devices

By using Bumble instead of the kernel's Bluetooth stack, we bypass the SMP bug entirely.

## Architecture

```
MediaTek MT8512 CONSYS
        |
        v
  /dev/stpbt (H4 HCI protocol)
        |
        v
  Bumble File Transport
        |
        v
  Bumble Host Stack
        |
        +---> SMP (Pairing/Encryption)
        |
        +---> GATT Client
        |         |
        |         v
        |     HID Service (0x1812)
        |         |
        |         v
        |     Report Characteristics
        |
        v
  /dev/uhid (Linux UHID)
        |
        v
  Linux Input Subsystem
        |
        v
  Applications (evtest, etc.)
```

## Status

**WORKING** - Implementation has been fixed and is compatible with Bumble 0.0.200.

See `API_FIXES.md` for details on Bumble 0.0.200 API compatibility fixes.

## Requirements

### On Kindle
- Python 3.8 (installed at `/mnt/us/python3.8-kindle/`)
- Google Bumble 0.0.200 library (installed)
- cryptography library with OpenSSL 3.x (installed)
- Root access

### Installation

All dependencies are already installed on the Kindle at:
- Python: `/mnt/us/python3.8-kindle/`
- Bumble: `/mnt/us/python3.8-kindle/bumble/`
- Script: `/mnt/us/bumble_ble_hid/kindle_ble_hid.py`

Use the wrapper script for easy execution:
```bash
/mnt/us/bumble_ble_hid/start_ble_hid.sh
```

## Usage

### Basic Usage (Scan and Connect)
```bash
./start_ble_hid.sh
```

This will:
1. Scan for BLE HID devices
2. Let you select one to connect to
3. Pair with the device
4. Create a virtual HID device via UHID
5. Forward HID reports to the system

### Connect to Specific Device
```bash
./start_ble_hid.sh -a AA:BB:CC:DD:EE:FF
```

### Debug Mode
```bash
./start_ble_hid.sh -d
```

### Manual Python Invocation
```bash
python3 kindle_ble_hid.py \
    --transport file:/dev/stpbt \
    --config device_config.json \
    --address AA:BB:CC:DD:EE:FF
```

## Transport Options

| Transport | Description |
|-----------|-------------|
| `file:/dev/stpbt` | Kindle's MediaTek STP Bluetooth (default) |
| `usb:0` | USB Bluetooth dongle |
| `hci-socket` | Linux HCI socket (requires BlueZ) |

## Files

| File | Description |
|------|-------------|
| `kindle_ble_hid.py` | Main BLE HID host implementation |
| `device_config.json` | Bumble device configuration |
| `start_ble_hid.sh` | Startup script |
| `requirements.txt` | Python dependencies |

## How It Works

### 1. Transport Layer
Bumble's file transport opens `/dev/stpbt` directly and uses H4 protocol framing to communicate with the Bluetooth controller.

### 2. BLE Scanning
The device scans for BLE advertisements and filters for devices advertising the HID service UUID (0x1812).

### 3. SMP Pairing
Bumble's SMP implementation handles:
- LE Secure Connections (LESC)
- Legacy pairing
- Just Works, Passkey Entry, Numeric Comparison
- Key generation and storage

### 4. GATT Service Discovery
After pairing, the host discovers:
- HID Service (0x1812)
- Report Map characteristic (HID descriptor)
- Report characteristics (input/output/feature)
- Report Reference descriptors

### 5. HID Report Handling
- Subscribe to input report notifications
- Parse incoming HID reports
- Forward to UHID for input injection

### 6. UHID Integration
The Linux UHID interface creates a virtual HID device that appears as a standard input device. HID reports are forwarded through this interface.

## Limitations

1. **Python Dependency**: Requires Python 3 runtime on the Kindle
2. **No BlueZ Integration**: This runs independently of BlueZ
3. **Single Device**: Currently connects to one HID device at a time
4. **Manual Reconnection**: No automatic reconnection on disconnect

## Troubleshooting

### "Permission denied" for /dev/stpbt
Run as root or ensure proper permissions:
```bash
chmod 666 /dev/stpbt
```

### "Permission denied" for /dev/uhid
Run as root or add to input group:
```bash
chmod 666 /dev/uhid
```

### No HID devices found
- Ensure the HID device is in pairing mode
- Check that the device advertises the HID service UUID
- Try increasing scan duration

### Pairing fails
- Some devices require specific IO capabilities
- Try different pairing modes (--io option in Bumble)
- Check device-specific pairing requirements

## References

- [Google Bumble](https://github.com/google/bumble)
- [Bumble Documentation](https://google.github.io/bumble/)
- [BLE HID Service Specification](https://www.bluetooth.com/specifications/specs/hid-service-1-0/)
- [Linux UHID Documentation](https://www.kernel.org/doc/html/latest/hid/uhid.html)

## Author

Lucas Zampieri <lzampier@redhat.com>
December 2025
