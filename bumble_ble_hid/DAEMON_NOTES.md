# BLE HID Daemon Notes

## Current Limitation: Single Device Only

**Important:** The current daemon implementation only supports connecting to ONE BLE HID device at a time.

### Why?

The `BLEHIDHost` class was designed for single-device usage (similar to the original interactive script). Key issues:

1. **Shared State:** `BLEHIDHost` stores connection state in instance variables (`self.connection`, `self.peer`, `self.uhid_device`)
2. **Transport:** Only one process can access `/dev/stpbt` at a time
3. **Device Instance:** One Bumble `Device` instance per daemon

### Current Behavior

If you configure multiple devices in `devices.conf`:
- Only the **first device** will be connected
- A warning is logged: "Multiple devices configured, but only connecting to first one"

### Configuration

Edit `/mnt/us/bumble_ble_hid/devices.conf`:

```bash
# Only ONE device will be connected (the first uncommented address)

# Device 1 (will connect)
5C:2B:3E:50:4F:04

# Device 2 (will be ignored)
# 11:22:33:33:DA:AF
```

To switch devices:
1. Comment out the current device with `#`
2. Uncomment the device you want to use
3. Restart the daemon: `/etc/init.d/ble-hid restart`

### Multi-Device Support (Future)

To support multiple devices simultaneously, `BLEHIDHost` would need refactoring:

1. **Connection Management:**
   ```python
   class BLEHIDHost:
       def __init__(self, transport):
           self.transport = transport
           self.device = None
           self.connections = {}  # address -> {peer, uhid, connection}

       async def connect_device(self, address):
           connection = await self.device.connect(address)
           peer = Peer(connection)
           # Store per-device state
           self.connections[address] = {
               'connection': connection,
               'peer': peer,
               'uhid': None,
               # ... other state
           }
   ```

2. **Event Handling:** Per-device event handlers instead of instance-level
3. **UHID Management:** One UHID device per connected BLE device
4. **Report Routing:** Route HID reports to correct UHID device based on source

### Workaround: Multiple Manual Connections

You can still connect to different devices manually using the helper script:

```bash
# Terminal 1: Connect to device 1
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh 5C:2B:3E:50:4F:04

# Terminal 2: Connect to device 2 (won't work - /dev/stpbt busy)
# This will fail with "Resource busy"
```

Unfortunately, even manual connections can't be parallel due to the `/dev/stpbt` limitation.

## Solutions for Multiple Devices

### Option 1: One Device at a Time (Current)
Use the daemon for your primary device, switch as needed.

### Option 2: Code Refactoring (Future)
Refactor `BLEHIDHost` to properly support multiple connections with one Device instance.

### Option 3: BlueZ + Userspace SMP (Alternative)
Use BlueZ for device management with a userspace SMP implementation (more complex).

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
