# Kindle BLE HID - Quick Start Guide

**SSH Access:** Use `ssh kindle` throughout this guide. The `kindle` hostname is already configured in `~/.ssh/config` and preferred over using the IP address directly.

## One-time Setup (already completed)

The Bumble BLE HID solution has been installed and configured on your Kindle.

## Connecting to BLE HID Devices

### Method 1: Using the Daemon (Persistent Connections)

The daemon automatically maintains connections to configured devices.

#### Scan for devices and add to configuration:

```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh
```

This will:
1. Scan for BLE HID devices (10 seconds)
2. Show you a list of found devices
3. Let you select which one to connect to

Once you know the device address, add it to the daemon config:

```bash
ssh kindle
echo "AA:BB:CC:DD:EE:FF" >> /mnt/us/bumble_ble_hid/devices.conf
```

#### Start the daemon:

```bash
ssh kindle
/etc/init.d/ble-hid start
```

#### Monitor daemon status:

```bash
# Check if running
ssh kindle '/etc/init.d/ble-hid status'

# View logs
ssh kindle 'tail -f /var/log/ble_hid_daemon.log'
```

#### Stop the daemon:

```bash
ssh kindle '/etc/init.d/ble-hid stop'
```

### Method 2: Manual Connection (One-time)

Connect to a specific device without persistent connection:

```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./kindle_ble_hid.sh AA:BB:CC:DD:EE:FF
```

## Current Configuration

Your daemon is configured to connect to:
- `5C:2B:3E:50:4F:04` (BLE-M3 Mouse)

**Important:** The daemon currently supports only **ONE device at a time**. If you configure multiple devices in `devices.conf`, only the first uncommented address will be used.

To switch devices:
1. Edit `/mnt/us/bumble_ble_hid/devices.conf`
2. Comment the current device with `#`
3. Uncomment the device you want
4. Restart: `ssh kindle '/etc/init.d/ble-hid restart'`

See `bumble_ble_hid/DAEMON_NOTES.md` for details on the single-device limitation.

## Troubleshooting

### Device won't connect
- Make sure the BLE device is powered on and in pairing mode
- Check logs: `ssh kindle 'tail -50 /var/log/ble_hid_daemon.log'`
- Try manual connection first to verify device is reachable

### Daemon won't start
- Check if another instance is running: `ssh kindle 'ps aux | grep ble_hid_daemon'`
- View full logs: `ssh kindle 'cat /var/log/ble_hid_daemon.log'`

### Connection drops frequently
- The daemon will automatically reconnect with exponential backoff (5s → 60s)
- Check for RF interference or distance issues

## Files and Locations

- Daemon script: `/mnt/us/bumble_ble_hid/ble_hid_daemon.py`
- Device config: `/mnt/us/bumble_ble_hid/devices.conf`
- Helper script: `/mnt/us/bumble_ble_hid/kindle_ble_hid.sh`
- Init script: `/etc/init.d/ble-hid`
- Daemon logs: `/var/log/ble_hid_daemon.log`

## Auto-start on Boot

To make the daemon start automatically when your Kindle boots:

```bash
ssh kindle
# Add to rc.local or your Kindle's startup script
echo "/etc/init.d/ble-hid start" >> /etc/rc.local
```
