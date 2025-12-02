# Usage Guide

## First Time Setup

### 1. Scan for Devices
```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh
```

Select your device from the list. It will connect, pair, and create a virtual HID device.

### 2. Add to Config
```bash
echo "AA:BB:CC:DD:EE:FF" >> /mnt/us/bumble_ble_hid/devices.conf
```

### 3. Start Daemon
```bash
/etc/init.d/ble-hid start
```

## Daily Use

### Start/Stop Daemon
```bash
/etc/init.d/ble-hid start   # Start
/etc/init.d/ble-hid stop    # Stop
/etc/init.d/ble-hid restart # Restart
/etc/init.d/ble-hid status  # Check status
```

### Monitor Connection
```bash
tail -f /var/log/ble_hid_daemon.log
```

### Manual Connection
```bash
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh AA:BB:CC:DD:EE:FF
```

## Multiple Devices

Edit `/mnt/us/bumble_ble_hid/devices.conf`:
```
# Gaming controller
11:22:33:33:DA:AF

# Keyboard
AA:BB:CC:DD:EE:FF

# Mouse
12:34:56:78:90:AB
```

Restart daemon:
```bash
/etc/init.d/ble-hid restart
```

## Troubleshooting

### Device not found during scan
1. Power on the device
2. Put device in pairing mode
3. Ensure device is in range

### Connection hangs
1. Check device is powered on
2. Try manual connection first
3. Check logs for errors

### Pairing fails
1. Remove device from other paired hosts
2. Power cycle the BLE device
3. Check device pairing requirements

### Daemon won't start
```bash
# Check if already running
ps aux | grep ble_hid_daemon

# Remove stale PID
rm -f /var/run/ble-hid.pid

# Check logs
cat /var/log/ble_hid_daemon.log
```

## Auto-start on Boot (Optional)

Add to `/etc/rc.local`:
```bash
/etc/init.d/ble-hid start
```
