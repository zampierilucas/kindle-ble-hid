# Kindle BLE HID Project

BLE HID device support for Amazon Kindle e-readers using Google Bumble.

## SSH Configuration

The Kindle is accessed via SSH using the host alias `kindle`.

## Deployment

Use `just` commands for all deployment and management:

```bash
just deploy       # Deploy files to Kindle and restart daemon
just deploy-watch # Deploy and follow logs
just ssh          # SSH into Kindle
```

## Daemon Management

```bash
just start        # Start daemon
just stop         # Stop daemon
just restart      # Restart daemon
just status       # Check daemon status
```

## Logs

```bash
just logs         # Follow daemon logs (tail -f)
just logs-recent  # Show last 50 lines
```

## Local Development

```bash
just check        # Check Python syntax
just test         # Run unit tests
```

## Cache Management

```bash
just clear-cache  # Clear GATT cache (forces rediscovery)
just show-cache   # Show cached device data
```

## File Locations on Kindle

- Code: `/mnt/us/bumble_ble_hid/`
- Init script: `/etc/init.d/ble-hid`
- Logs: `/var/log/ble_hid_daemon.log`
- Device config: `/mnt/us/bumble_ble_hid/devices.conf`
