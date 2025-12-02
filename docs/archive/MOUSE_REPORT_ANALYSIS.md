# Mouse Report Analysis - Logitech M720

## Problem

The Logitech M720 BLE mouse has a firmware bug where it sends HID reports with IDs that don't match its declared HID report descriptor.

### HID Report Descriptor declares:
- Report ID 1: Digitizer (touchscreen with absolute X/Y)
- Report ID 2: Consumer controls (media buttons)
- Report ID 3: Keyboard

### Actual reports being sent:
- Report ID 0x00: `0096008601` (5 bytes)
- Report ID 0x07: `0768019001` (5 bytes)

## Report Format Analysis

Looking at the actual reports:
```
0768019001 -> ID=07, buttons=68, x=01, y=90, wheel=01
07fa008601 -> ID=07, buttons=fa, x=00, y=86, wheel=01
0796009001 -> ID=07, buttons=96, x=00, y=90, wheel=01
0096008601 -> ID=00, buttons=96, x=00, y=86, wheel=01
```

These appear to be standard 5-byte mouse reports:
- Byte 0: Report ID
- Byte 1: Button state
- Byte 2: X movement (signed)
- Byte 3: Y movement (signed)
- Byte 4: Wheel movement (signed)

## Solution Options

### Option 1: Fix the report descriptor (RECOMMENDED)
Intercept the report map during UHID creation and inject proper mouse descriptors for IDs 0 and 7.

### Option 2: Translate reports
Convert incoming reports to match the declared format (Report ID 1 - digitizer).

### Option 3: Create separate UHID device
Create a second UHID device with a proper mouse descriptor and route ID 0/7 reports to it.

## Implementation

We'll go with Option 1 - patch the report descriptor to include mouse reports.
