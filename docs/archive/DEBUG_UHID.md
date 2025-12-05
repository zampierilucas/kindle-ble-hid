# Debugging UHID Input Issues

You're seeing HID reports in the daemon logs but not getting input events. Let's debug this systematically.

## Step 1: Verify UHID Kernel Support

Check if your kernel has UHID support:

```bash
ssh kindle
zcat /proc/config.gz | grep UHID
```

Expected output:
```
CONFIG_UHID=y
```

If UHID is not enabled (`CONFIG_UHID is not set`), the kernel doesn't support UHID and we'll need an alternative approach.

## Step 2: Test Basic UHID Functionality

Copy the test script to Kindle:

```bash
scp test_uhid_simple.py kindle:/tmp/
ssh kindle
cd /tmp
python3 test_uhid_simple.py
```

This will:
1. Create a virtual mouse device via UHID
2. Send test mouse movements
3. Show you if UHID is working

While it's running, check for new input device:
```bash
# In another SSH session
ssh kindle
ls -l /dev/input/
cat /proc/bus/input/devices | grep -A 5 "Test BLE Mouse"
```

## Step 3: Monitor UHID Events

Copy the debug monitor to Kindle:

```bash
scp debug_uhid.py kindle:/tmp/
ssh kindle
cd /tmp
python3 debug_uhid.py
```

Leave this running, then start your BLE HID daemon in another terminal:

```bash
ssh kindle
/etc/init.d/ble-hid start
```

The monitor will show:
- When UHID device is created (UHID_CREATE2)
- When kernel starts using it (UHID_START, UHID_OPEN)
- When input reports are sent (UHID_INPUT2)

## Step 4: Verify Event Device Mapping

Find which event device corresponds to your BLE HID device:

```bash
ssh kindle
cat /proc/bus/input/devices
```

Look for a device with:
- Name containing "BLE HID" or your device name
- Phys containing "bumble:ble-hid"
- Handlers showing "eventX"

Example output:
```
I: Bus=0005 Vendor=0001 Product=0001 Version=0001
N: Name="BLE HID 5C:2B:3E:50:4F:04"
P: Phys=bumble:ble-hid
S: Sysfs=/devices/virtual/input/input3
U: Uniq=
H: Handlers=event2 mouse0
B: PROP=0
```

In this example, it's `/dev/input/event2`.

## Step 5: Monitor Input Events

Use `evtest` to watch for events on the correct device:

```bash
ssh kindle
evtest /dev/input/event2  # Use your actual eventX
```

Then trigger some input on your BLE device (move mouse, press key). You should see events appear.

## Common Issues and Solutions

### Issue 1: No eventX device created after UHID_CREATE2

**Symptom:** UHID device created but no `/dev/input/eventX` appears

**Possible causes:**
1. Invalid HID report descriptor
2. Kernel UHID driver not loading input subsystem
3. Kernel version incompatibility

**Debug:**
```bash
# Check kernel logs
dmesg | tail -50

# Look for errors like:
# - "hid-generic: ignoring report descriptor"
# - "input: failed to register device"
```

**Solution:** Check the HID report descriptor being used. Compare with the test script's simple mouse descriptor.

### Issue 2: Device created but no events on movement

**Symptom:** `/dev/input/eventX` exists, evtest shows device, but no events

**Possible causes:**
1. Input reports not reaching UHID
2. Wrong report format
3. Report descriptor mismatch

**Debug steps:**

1. Verify reports are reaching UHID (use debug_uhid.py)
2. Check report format matches descriptor
3. Compare HID report hex with descriptor expectations

Example: Your mouse reports look like `0296008601` (5 bytes). This should match what the HID report descriptor expects.

### Issue 3: Reports in log but not in UHID monitor

**Symptom:** Daemon shows ">>> HID Report: 0296008601" but debug_uhid.py shows no UHID_INPUT2

**Possible cause:** UHID device not created or send_input() failing silently

**Debug:** Add logging to kindle_ble_hid.py in the UHIDDevice.send_input() method:

```python
def send_input(self, report_data: bytes):
    """Send an input report to the virtual HID device"""
    if not self.running or self.fd is None:
        logging.error(f"Cannot send input: running={self.running}, fd={self.fd}")
        return

    logging.debug(f"Sending UHID_INPUT2: {report_data.hex()}")

    event = struct.pack('<I', UHID_INPUT2)
    event += struct.pack('<H', len(report_data))
    event += report_data.ljust(4096, b'\x00')

    try:
        bytes_written = os.write(self.fd, event)
        logging.debug(f"Wrote {bytes_written} bytes to UHID")
    except OSError as e:
        logging.error(f"Failed to send input report: {e}")
```

### Issue 4: Wrong event device

**Symptom:** Monitoring event0 or event1 but BLE HID is actually event2

**Solution:** Always check `/proc/bus/input/devices` to find the correct device

## Quick Diagnostic Checklist

Run this on Kindle while BLE device is connected and daemon is running:

```bash
#!/bin/sh
echo "=== UHID Diagnostic ==="
echo ""

echo "1. Kernel UHID support:"
zcat /proc/config.gz | grep UHID

echo ""
echo "2. Input devices:"
ls -l /dev/input/

echo ""
echo "3. Registered input devices:"
cat /proc/bus/input/devices | grep -E "^(I:|N:|P:|H:)"

echo ""
echo "4. UHID device status:"
ls -l /dev/uhid

echo ""
echo "5. Recent kernel messages:"
dmesg | tail -20 | grep -i "input\|hid\|uhid"

echo ""
echo "6. BLE HID daemon status:"
ps aux | grep ble_hid_daemon

echo ""
echo "7. Daemon log (last 10 lines):"
tail -10 /var/log/ble_hid_daemon.log
```

Save as `/tmp/uhid_diagnostic.sh` and run it.

## Next Steps

Based on your test results:

1. **If test_uhid_simple.py works:** UHID is functional, issue is in daemon's HID report handling
2. **If test_uhid_simple.py fails:** Kernel doesn't support UHID properly
3. **If debug_uhid.py shows UHID_INPUT2 but no events:** Report descriptor or format issue

Let me know what you find and we'll debug further!
