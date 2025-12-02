# Bluetooth Module Fix

## Problem

The `/dev/stpbt` Bluetooth device was not appearing on the Kindle, causing the BLE HID daemon to fail with:

```
FileNotFoundError: [Errno 2] No such file or directory: '/dev/stpbt'
```

## Root Cause

The `wmt_cdev_bt` kernel module, which creates the `/dev/stpbt` character device, was not being loaded on boot. While the WiFi variant (`wmt_chrdev_wifi`) was loaded, the Bluetooth variant was missing.

## Investigation Steps

1. Verified the module exists: `/lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko`
2. Checked module dependencies with `modinfo`: depends on `wmt_drv` (which was already loaded)
3. Successfully loaded the module manually: `/sbin/insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko`
4. Confirmed `/dev/stpbt` was created after module load: `crw-rw---- 1 root bluetoot 192, 0`

## Solution

Modified the BLE HID init script (`/etc/init.d/ble-hid`) to automatically load the kernel module on daemon start:

```bash
# Load Bluetooth kernel module if not loaded
if ! lsmod | grep -q wmt_cdev_bt; then
    echo "Loading wmt_cdev_bt kernel module..."
    /sbin/insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko
    sleep 1
fi

# Verify /dev/stpbt exists
if [ ! -c /dev/stpbt ]; then
    echo "ERROR: /dev/stpbt device not available"
    return 1
fi
```

## Files Modified

- **`bumble_ble_hid/ble-hid.init`**: Local copy of init script with module loading
- **`justfile`**: Updated deploy recipe to copy init script to `/etc/init.d/ble-hid`

## Deployment

The fix is automatically deployed with:

```bash
just deploy
```

This will:
1. Copy the updated init script to the Kindle
2. Ensure it's executable
3. Restart the daemon

## Verification

Check that the module is loaded and daemon is working:

```bash
# Check module is loaded
ssh kindle "lsmod | grep wmt_cdev_bt"

# Check device exists
ssh kindle "ls -la /dev/stpbt"

# Check daemon status
just status

# View logs
just logs-recent
```

Expected output:
- Module: `wmt_cdev_bt 17908 0`
- Device: `crw-rw---- 1 root bluetoot 192, 0 /dev/stpbt`
- Daemon: Successfully creating Bumble hosts and attempting connections

## Technical Details

### MediaTek CONSYS Architecture

The Kindle uses a MediaTek MT8512 combo chip with the following architecture:

```
MediaTek MT8512 CONSYS (WiFi/BT Combo Chip)
        |
        v
   WMT Driver (wmt_drv)
        |
        +---> wmt_chrdev_wifi --> WiFi interface
        |
        +---> wmt_cdev_bt --> /dev/stpbt (Bluetooth)
        |
        v
  STP Protocol (Serial Transport Protocol)
        |
        v
  H4 HCI Protocol
        |
        v
  Bumble BLE Stack
```

### Device Node

- **Path**: `/dev/stpbt`
- **Type**: Character device
- **Major:Minor**: 192:0
- **Permissions**: `crw-rw----` (root:bluetoot)
- **Created by**: `wmt_cdev_bt.ko` kernel module

### Kernel Module

- **Path**: `/lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko`
- **Size**: 17908 bytes
- **Dependencies**: `wmt_drv` (core WMT driver)
- **License**: Dual BSD/GPL
- **Load command**: `/sbin/insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko`

## Why This Wasn't Loaded by Default

Amazon's BT stack services (`btmanagerd`, `acsbtfd`) were disabled to allow custom Bluetooth implementations. These services likely loaded the `wmt_cdev_bt` module as part of their initialization. Since we're using Bumble instead of Amazon's stack, we need to load the module manually.

## Future Considerations

An alternative approach would be to add the module to `/etc/modules` or create a modprobe configuration, but the current init script approach is simpler and keeps all BLE HID setup logic in one place.

## Status

**FIXED** - The daemon now successfully loads the kernel module on startup and can communicate with the MediaTek Bluetooth controller via `/dev/stpbt`.

## Author

Lucas Zampieri <lzampier@redhat.com>
December 2, 2025
