# Usage Examples

## Connecting to a New BLE HID Device

### Step 1: Scan for Devices

```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh
```

**Output:**
```
=== Kindle BLE HID Host ===

Stopping existing Bluetooth processes...

Starting BLE HID Host...
Transport: file:/dev/stpbt

>>> Opening transport...
>>> Device powered on: 00:00:46:67:61:01/P
>>> Scanning for BLE HID devices...
>>> Scan complete. Found 2 devices.

Select device:
  1. Dactyl 5x6 (E2:A0:38:99:42:67)
  2. Beauty-R1 (11:22:33:33:DA:AF)

Enter number:
```

Type the number of your device and press Enter.

### Step 2: Connection Process

The script will automatically:
1. Connect to the device
2. Pair (if needed)
3. Discover HID services
4. Read Report Map
5. Subscribe to HID input reports
6. Create UHID virtual device

**Example successful connection:**
```
>>> Connecting to 11:22:33:33:DA:AF...
>>> Connected to 11:22:33:33:DA:AF
>>> Attempting pairing...
>>> Pairing successful!
>>> HID Service found
>>> Discovering characteristics...
>>> Found 5 characteristics in HID service
>>> Report Map (114 bytes): 05010906...
>>> Subscribed to input report (ID: 1, Type: 1)
>>> UHID device created: BLE HID 11:22:33:33:DA:AF

>>> Receiving HID reports. Press Ctrl+C to exit.
```

### Step 3: Test the Device

Your BLE HID device should now work! Try pressing buttons/keys and see if they register.

Press Ctrl+C to disconnect when done.

## Adding Device to Persistent Configuration

Once you know the device address, add it to the daemon configuration:

```bash
ssh kindle
echo "11:22:33:33:DA:AF" >> /mnt/us/bumble_ble_hid/devices.conf
```

**Current devices.conf:**
```
# BLE HID Device Configuration
# Add one device address per line
# Lines starting with # are comments

# Beauty-R1 Remote Controller
11:22:33:33:DA:AF
```

## Using the Daemon

### Start the Daemon

```bash
ssh kindle '/etc/init.d/ble-hid start'
```

**Output:**
```
Starting BLE HID daemon...
BLE HID daemon started (PID: 12345)
```

### Monitor Connection Progress

```bash
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

**Example log output:**
```
2025-12-01 21:30:00,123 INFO __main__: Loaded 1 device(s) from config
2025-12-01 21:30:00,125 INFO __main__: Connecting to 11:22:33:33:DA:AF...
2025-12-01 21:30:00,127 INFO __main__: Starting Bumble host for 11:22:33:33:DA:AF...
2025-12-01 21:30:00,315 INFO __main__: Connecting to device 11:22:33:33:DA:AF...
2025-12-01 21:30:05,892 INFO __main__: Pairing with 11:22:33:33:DA:AF...
2025-12-01 21:30:06,234 INFO __main__: Discovering HID service on 11:22:33:33:DA:AF...
2025-12-01 21:30:07,456 INFO __main__: Creating UHID device for 11:22:33:33:DA:AF...
2025-12-01 21:30:07,567 INFO __main__: Successfully connected to 11:22:33:33:DA:AF
```

Press Ctrl+C to stop following the log.

### Check Daemon Status

```bash
ssh kindle '/etc/init.d/ble-hid status'
```

**Output if running:**
```
BLE HID daemon is running (PID: 12345)
```

**Output if stopped:**
```
BLE HID daemon is not running
```

### Stop the Daemon

```bash
ssh kindle '/etc/init.d/ble-hid stop'
```

**Output:**
```
Stopping BLE HID daemon...
BLE HID daemon stopped
```

## Reconnection Behavior

The daemon automatically reconnects when a device disconnects:

**Example reconnection log:**
```
2025-12-01 21:35:12,789 WARNING __main__: Disconnected from 11:22:33:33:DA:AF
2025-12-01 21:35:12,790 INFO __main__: Reconnecting to 11:22:33:33:DA:AF in 5 seconds...
2025-12-01 21:35:17,795 INFO __main__: Connecting to 11:22:33:33:DA:AF...
2025-12-01 21:35:17,797 INFO __main__: Starting Bumble host for 11:22:33:33:DA:AF...
...
2025-12-01 21:35:25,123 INFO __main__: Successfully connected to 11:22:33:33:DA:AF
```

If connection fails, it uses exponential backoff (5s → 10s → 20s → 40s → 60s max).

## Multiple Devices

You can configure multiple devices in `devices.conf`:

```
# BLE HID Device Configuration

# Gaming controller
11:22:33:33:DA:AF

# Bluetooth keyboard
AA:BB:CC:DD:EE:FF

# Bluetooth mouse
12:34:56:78:90:AB
```

The daemon will connect to all of them in parallel and maintain all connections.

## Connect to Specific Device (Manual)

If you know the device address, you can connect directly:

```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh 11:22:33:33:DA:AF
```

This skips the scanning step and connects immediately.

## Troubleshooting

### Device not found during scan

**Problem:** Scan completes but shows "No HID devices found!"

**Solutions:**
1. Make sure the device is powered on
2. Make sure the device is in pairing/advertising mode
3. Some devices stop advertising after a timeout - power cycle the device
4. Try increasing scan duration by editing `kindle_ble_hid.py` (line 455, change `duration=10.0` to `duration=30.0`)

### Connection hangs at "Connecting to device"

**Problem:** Daemon logs show "Connecting to device..." but never progresses

**Solutions:**
1. Make sure the device is powered on and advertising
2. Make sure the device is in range
3. Try connecting manually first: `./kindle_ble_hid.sh DEVICE_ADDR`
4. Check for RF interference or distance issues

### Pairing fails

**Problem:** Connection succeeds but pairing fails

**Solutions:**
1. Some devices need to be put in pairing mode manually
2. Try removing the device from any other paired host first
3. Power cycle the BLE device
4. Check logs for specific pairing error

### UHID device not created

**Problem:** Connection and pairing succeed, but no input is registered

**Solutions:**
1. Check if UHID module is loaded: `ssh kindle 'lsmod | grep uhid'`
2. Load UHID module: `ssh kindle 'modprobe uhid'`
3. Check logs for HID service discovery errors
4. Verify device permissions on `/dev/uhid`

### Daemon won't start

**Problem:** `/etc/init.d/ble-hid start` fails

**Solutions:**
1. Check if already running: `ssh kindle 'ps aux | grep ble_hid_daemon'`
2. Check for stale PID file: `ssh kindle 'rm -f /var/run/ble-hid.pid'`
3. View full logs: `ssh kindle 'cat /var/log/ble_hid_daemon.log'`
