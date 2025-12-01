# BLE HID Daemon Installation Summary

**Date:** December 1, 2025

## What Was Installed

A complete persistent BLE HID connection system for your Kindle, consisting of:

### 1. Core Daemon (`ble_hid_daemon.py`)

**Location:** `/mnt/us/bumble_ble_hid/ble_hid_daemon.py`

**Features:**
- Maintains persistent connections to configured BLE HID devices
- Automatic reconnection with exponential backoff (5s → 60s)
- Handles multiple devices in parallel
- Detailed logging to `/var/log/ble_hid_daemon.log`
- Graceful shutdown on SIGTERM/SIGINT

**How it works:**
1. Reads device addresses from `devices.conf`
2. Creates a connection task for each device
3. For each device:
   - Opens Bumble transport
   - Connects to device
   - Performs SMP pairing
   - Discovers HID service
   - Creates UHID virtual input device
   - Waits for disconnection
4. On disconnection, automatically reconnects with backoff
5. On error, logs the issue and retries

### 2. Init Script (`/etc/init.d/ble-hid`)

**Location:** `/etc/init.d/ble-hid`

**Commands:**
- `start` - Start the daemon in background
- `stop` - Stop the daemon gracefully
- `restart` - Stop then start
- `status` - Check if daemon is running

**Features:**
- PID file management (`/var/run/ble-hid.pid`)
- Automatic cleanup of conflicting Bluetooth processes
- Graceful shutdown with SIGTERM, then SIGKILL if needed

### 3. Device Configuration (`devices.conf`)

**Location:** `/mnt/us/bumble_ble_hid/devices.conf`

**Format:**
```
# Comment lines start with #
DEVICE_ADDRESS_1
DEVICE_ADDRESS_2
...
```

**Current configuration:**
- `11:22:33:33:DA:AF` (Beauty-R1 Remote Controller)

Add more devices by appending addresses to this file.

### 4. Helper Script (`kindle_ble_hid.sh`)

**Location:** `/mnt/us/bumble_ble_hid/kindle_ble_hid.sh`

**Usage:**
- `./kindle_ble_hid.sh` - Scan and select device
- `./kindle_ble_hid.sh ADDRESS` - Connect to specific device

**Features:**
- No bash-specific syntax (works with busybox ash/sh)
- Automatic Bluetooth process cleanup
- Proper argument handling

**Replaces:** Old broken `start_ble_hid.sh` (removed)

## File Structure

```
/mnt/us/bumble_ble_hid/
├── ble_hid_daemon.py          # Persistent connection daemon
├── devices.conf                # Device address configuration
├── kindle_ble_hid.py           # Main BLE HID implementation
├── kindle_ble_hid.sh           # Helper script (NEW)
└── device_config.json          # Device-specific config (if needed)

/etc/init.d/
└── ble-hid                     # Init script for daemon control

/var/log/
└── ble_hid_daemon.log          # Daemon log file

/var/run/
└── ble-hid.pid                 # Daemon PID file (when running)
```

## Usage Examples

### Start persistent connection
```bash
ssh kindle '/etc/init.d/ble-hid start'
```

### Monitor connection
```bash
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

### Stop daemon
```bash
ssh kindle '/etc/init.d/ble-hid stop'
```

### Scan for new devices
```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh
```

### Add device to auto-connect
```bash
ssh kindle
echo "AA:BB:CC:DD:EE:FF" >> /mnt/us/bumble_ble_hid/devices.conf
/etc/init.d/ble-hid restart
```

## Auto-start on Boot (Optional)

To make the daemon start automatically when Kindle boots:

```bash
ssh kindle
# Add to your Kindle's startup script (e.g., /etc/rc.local)
echo "/etc/init.d/ble-hid start" >> /etc/rc.local
```

Or create a udev rule if your Kindle supports it.

## Logs and Debugging

### View daemon logs
```bash
ssh kindle 'tail -50 /var/log/ble_hid_daemon.log'
```

### Follow logs in real-time
```bash
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

### Check daemon process
```bash
ssh kindle 'ps aux | grep ble_hid_daemon'
```

### View daemon PID
```bash
ssh kindle 'cat /var/run/ble-hid.pid'
```

## Differences from Manual Connection

### Manual Connection (`./kindle_ble_hid.sh`)
- One-time connection
- Interactive (scan/select)
- Runs in foreground
- Exits on disconnection
- Good for testing

### Daemon Connection (`/etc/init.d/ble-hid`)
- Persistent connection
- Non-interactive (uses config file)
- Runs in background
- Auto-reconnects on disconnection
- Good for daily use

## Technical Details

### Reconnection Logic

The daemon uses exponential backoff for reconnection:
1. First retry: 5 seconds
2. Second retry: 10 seconds
3. Third retry: 20 seconds
4. Fourth retry: 40 seconds
5. Further retries: 60 seconds (max)

On successful connection, the delay resets to 5 seconds.

### Error Handling

The daemon catches and logs all exceptions:
- Connection errors → logged and retry scheduled
- Pairing failures → logged and retry scheduled
- HID discovery failures → logged, cleanup, retry scheduled
- Keyboard interrupt (Ctrl+C) → graceful shutdown
- SIGTERM/SIGINT → graceful shutdown via signal handler

### Resource Cleanup

On shutdown or error:
1. Cancel all connection tasks
2. Close all UHID devices
3. Disconnect all BLE connections
4. Close Bumble transport
5. Remove PID file

## What Changed from Previous Setup

1. **Removed:** `start_ble_hid.sh` (broken bash syntax)
2. **Added:** `kindle_ble_hid.sh` (POSIX shell compatible)
3. **Added:** `ble_hid_daemon.py` (persistent connection daemon)
4. **Added:** `/etc/init.d/ble-hid` (init script)
5. **Added:** `devices.conf` (device configuration)
6. **Added:** Logging to `/var/log/ble_hid_daemon.log`

## Next Steps

1. Power on your BLE HID device
2. Start the daemon: `ssh kindle '/etc/init.d/ble-hid start'`
3. Monitor logs: `ssh kindle 'tail -f /var/log/ble_hid_daemon.log'`
4. Test your device!

## See Also

- `QUICK_START.md` - Quick reference guide
- `USAGE_EXAMPLES.md` - Detailed usage examples
- `bumble_ble_hid/README.md` - Implementation details
- `BUMBLE_BLE_HID_FIXES.md` - API compatibility fixes
