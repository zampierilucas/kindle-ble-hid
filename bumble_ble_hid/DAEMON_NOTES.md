# BLE HID Daemon Notes

## Multi-Device Support

The daemon now supports **multiple BLE HID devices simultaneously**:

- Each device gets its own dedicated Bumble host instance
- Devices run in parallel with independent connection/reconnection logic
- Add multiple device addresses to `/mnt/us/bumble_ble_hid/devices.conf` (one per line)
- Each device creates its own UHID virtual input device

### Configuration

Edit `/mnt/us/bumble_ble_hid/devices.conf`:

```bash
# Multiple devices - all will connect
5C:2B:3E:50:4F:04  # BLE-M3 Mouse
AA:BB:CC:DD:EE:FF  # Keyboard
11:22:33:44:55:66  # Gamepad

# Comment out devices you don't want to connect
# 99:88:77:66:55:44
```

### How It Works

1. **Separate Host Instances:** Each device gets its own `BLEHIDHost` instance with dedicated state
2. **Parallel Connections:** All devices connect concurrently via `asyncio.gather()`
3. **Independent Reconnection:** Each device has its own reconnection logic and timing
4. **Shared Transport:** All hosts share the same `/dev/stpbt` transport (Bumble handles multiplexing)

### Architecture

```
/dev/stpbt (MediaTek BT Controller)
     |
     v
Bumble Transport (shared)
     |
     +---> BLEHIDHost #1 ---> Device 1 ---> /dev/uhid ---> Input Device 1
     |
     +---> BLEHIDHost #2 ---> Device 2 ---> /dev/uhid ---> Input Device 2
     |
     +---> BLEHIDHost #3 ---> Device 3 ---> /dev/uhid ---> Input Device 3
```

## Pure Pass-Through Mode

By default, the daemon operates in **pure pass-through mode**:
- HID reports are forwarded unchanged to UHID
- No device-specific button mapping or translation
- Works with any BLE HID device (keyboards, mice, gamepads, etc.)

### Legacy BLE-M3 Mode

For backwards compatibility with the BLE-M3 clicker, you can enable legacy mode:

```bash
export KINDLE_BLE_HID_PATCH_DESCRIPTOR=1
/etc/init.d/ble-hid start
```

This enables:
- Report descriptor patching (adds button report IDs)
- BLE-M3 specific button mapping
- Movement-based button detection
- 500ms debouncing

**Note:** For new projects, use pure pass-through mode and handle device-specific logic in a separate userspace daemon.

## Device-Specific Input Translation

For devices that need custom input mapping (like the BLE-M3 clicker), create a separate userspace daemon:

1. **BLE Stack (this project):** Handles BLE connection, pairing, and raw HID report forwarding
2. **Input Translator (separate daemon):** Monitors `/dev/input/eventX`, translates events, injects via `uinput`

This separation follows Unix philosophy and allows:
- Reusable BLE HID stack for all devices
- Device-specific logic isolated and testable
- Easier maintenance and debugging

Example: See `/home/lzampier/Clone/BLE-M3-android-interceptor/` for a C-based input translator.

## Limitations

1. **Python runtime**: Requires Python 3.8 on device
2. **Power consumption**: Continuous BLE scanning/connection may impact battery life
3. **Shared transport**: All devices must use the same Bluetooth controller (`/dev/stpbt`)

## Error: "Resource busy: '/dev/stpbt'"

This error occurs when:
1. Multiple daemon instances try to start
2. Manual script is running while daemon starts
3. Previous process didn't clean up properly

**Fix:**
```bash
# Stop all processes
ssh kindle
killall ble_hid_daemon.py
killall kindle_ble_hid.py
/etc/init.d/ble-hid stop

# Wait a moment
sleep 2

# Restart
/etc/init.d/ble-hid start
```

## Reconnection Strategy

The daemon uses activity-aware reconnection delays:

- **Active Mode** (user input detected in last 60s): Reconnect every 3 seconds
- **Idle Mode** (no input for 60s): Reconnect every 30 seconds

This reduces battery drain when the Kindle is not in use while maintaining responsive reconnection during active use.
