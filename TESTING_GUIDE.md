# Bumble BLE HID - Testing Guide

## Quick Reference

### Device
- Kindle IP: `192.168.0.65`
- Login: `ssh root@192.168.0.65` (or `ssh kindle`)

### Main Script
- Location: `/mnt/us/bumble_ble_hid/kindle_ble_hid.py`
- Wrapper: `/mnt/us/bumble_ble_hid/start_ble_hid.sh`

## Test Scenarios

### Test 1: Scan for BLE Devices

**Purpose:** Verify scanning works and can detect BLE HID devices

**Steps:**
```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./start_ble_hid.sh
```

**Expected Output:**
```
>>> Opening transport...
>>> Device powered on: F0:F0:F0:F0:F0:F0
>>> Scanning for 10.0 seconds...
    Found: Device Name (AA:BB:CC:DD:EE:FF) RSSI: -50 [HID]
    Found: Another Device (11:22:33:44:55:66) RSSI: -60
>>> Scan complete. Found 2 devices.
```

**Success Criteria:**
- Transport opens without errors
- Device powers on
- Scanning completes
- BLE HID devices show `[HID]` marker

### Test 2: Connect to Specific Device

**Purpose:** Verify connection to a known BLE HID device

**Prerequisites:**
- Put BLE device in pairing mode
- Note the device MAC address from Test 1

**Steps:**
```bash
ssh kindle
cd /mnt/us/bumble_ble_hid
./start_ble_hid.sh -a AA:BB:CC:DD:EE:FF
```

**Expected Output:**
```
>>> Opening transport...
>>> Device powered on: F0:F0:F0:F0:F0:F0
>>> Connecting to AA:BB:CC:DD:EE:FF...
>>> Connected to AA:BB:CC:DD:EE:FF
>>> Initiating pairing...
>>> Pairing request received - accepting
>>> Pairing complete!
>>> Discovering GATT services...
>>> Found HID service: 00001812-0000-1000-8000-00805f9b34fb
    Characteristic: 00002a4b-0000-1000-8000-00805f9b34fb
    Report Map: 52 bytes
    Characteristic: 00002a4d-0000-1000-8000-00805f9b34fb
    Report ID: 0, Type: 1
    Subscribed to input report 0
Created UHID device: BLE HID Device

>>> Receiving HID reports. Press Ctrl+C to exit.
```

**Success Criteria:**
- Connection established
- Pairing successful (no SMP errors)
- HID service discovered
- Report map read successfully
- Input reports subscribed
- UHID device created

### Test 3: Receive HID Reports

**Purpose:** Verify HID input is received from the device

**Prerequisites:**
- Complete Test 2 successfully
- Keep the script running

**Steps:**
1. Press keys on the keyboard (or move mouse/press gamepad buttons)
2. Observe HID report output

**Expected Output:**
```
>>> HID Report: 0000000000000000
>>> HID Report: 0000040000000000  (key 'a' pressed)
>>> HID Report: 0000000000000000  (key released)
```

**Success Criteria:**
- HID reports show up when interacting with device
- Report data changes based on input
- No errors in console

### Test 4: Test Input Injection

**Purpose:** Verify UHID creates a working input device

**Prerequisites:**
- Complete Test 2 successfully
- Open a second SSH session to the Kindle

**Steps (in second SSH session):**
```bash
# List input devices
ls -l /dev/input/event*

# Find the UHID device (usually newest event number)
evtest /dev/input/event3  # Adjust number as needed

# Or monitor all events
cat /proc/bus/input/devices | grep -A 5 "BLE HID"
```

**Expected Output:**
```
Input driver version is 1.0.1
Input device ID: bus 0x5 vendor 0x1 product 0x1 version 0x1
Input device name: "BLE HID Device"
Supported events:
  Event type 0 (EV_SYN)
  Event type 1 (EV_KEY)
    Event code 30 (KEY_A)
    Event code 48 (KEY_B)
    ...
```

**Success Criteria:**
- UHID device appears in `/dev/input/`
- Device is visible in `/proc/bus/input/devices`
- `evtest` shows input events when you press keys/buttons
- Events correspond to actual input on HID device

## Debug Mode

For detailed logging:
```bash
./start_ble_hid.sh -d -a AA:BB:CC:DD:EE:FF
```

This shows:
- HCI packet traces
- GATT operations
- SMP negotiation details
- Detailed error messages

## Common Issues

### Issue: "Permission denied" for /dev/stpbt
**Solution:**
```bash
chmod 666 /dev/stpbt
```

### Issue: "Permission denied" for /dev/uhid
**Solution:**
```bash
chmod 666 /dev/uhid
```

### Issue: No HID devices found
**Causes:**
- Device not in pairing mode
- Device not advertising HID service
- Out of range

**Solutions:**
- Put device in pairing mode (usually hold pairing button)
- Move closer to Kindle
- Try increasing scan duration by editing `kindle_ble_hid.py`

### Issue: Pairing fails
**Causes:**
- Wrong IO capability
- Device requires specific pairing method
- Device already bonded to another host

**Solutions:**
- Reset/unpair device from other hosts
- Try different pairing modes (edit SimplePairingDelegate in script)
- Check device documentation for pairing requirements

### Issue: Connected but no HID reports
**Causes:**
- Report notifications not enabled
- Wrong characteristic subscribed
- Device in sleep mode

**Solutions:**
- Check debug output for subscription errors
- Wake device (press keys/buttons)
- Verify Report Map was read successfully

## Useful Commands

### Check if Bluetooth hardware is responsive
```bash
cat /dev/stpbt  # Should block waiting for data
# Press Ctrl+C to exit
```

### Monitor HCI traffic (if hcidump is available)
```bash
hcidump -x -i hci0
```

### Check Python imports
```bash
/mnt/us/python3.8-kindle/python3-wrapper.sh -c "import bumble; import cryptography; print('OK')"
```

### Kill running Bumble processes
```bash
killall python3.8
```

### Check UHID device status
```bash
cat /proc/bus/input/devices | grep -A 10 "BLE HID"
```

## Test Devices

Recommended test devices:
- **Keyboards:** Most Bluetooth keyboards advertise HID service
- **Mice:** BLE mice with HID profile
- **Game Controllers:** Xbox/PS controllers in BLE mode
- **Cheap BLE Keyboard:** Easy to find and test with

## Success Indicators

1. Transport opens without "Operation not permitted" errors
2. Device powers on and gets address F0:F0:F0:F0:F0:F0
3. Scanning finds devices with `[HID]` marker
4. Connection establishes without timeout
5. Pairing completes with "Pairing successful!" message
6. HID service UUID (00001812...) is discovered
7. Report Map is read (shows byte count)
8. Input reports are subscribed
9. UHID device is created
10. HID reports appear when device input occurs
11. evtest shows corresponding Linux input events

## Author
Lucas Zampieri <lzampier@redhat.com>
