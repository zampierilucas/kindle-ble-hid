#!/usr/bin/env python3
"""
Simple UHID test - creates a virtual mouse and sends test input

This will verify if UHID is working on your Kindle kernel.

Usage on Kindle:
    python3 test_uhid_simple.py
"""

import os
import struct
import time

UHID_CREATE2 = 11
UHID_INPUT2 = 12
UHID_DESTROY = 1

# Simple mouse HID report descriptor
# 3 bytes: [buttons, x, y]
MOUSE_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x02,        # Usage (Mouse)
    0xA1, 0x01,        # Collection (Application)
    0x09, 0x01,        #   Usage (Pointer)
    0xA1, 0x00,        #   Collection (Physical)
    0x05, 0x09,        #     Usage Page (Button)
    0x19, 0x01,        #     Usage Minimum (1)
    0x29, 0x03,        #     Usage Maximum (3)
    0x15, 0x00,        #     Logical Minimum (0)
    0x25, 0x01,        #     Logical Maximum (1)
    0x95, 0x03,        #     Report Count (3)
    0x75, 0x01,        #     Report Size (1)
    0x81, 0x02,        #     Input (Data, Variable, Absolute)
    0x95, 0x01,        #     Report Count (1)
    0x75, 0x05,        #     Report Size (5)
    0x81, 0x01,        #     Input (Constant)
    0x05, 0x01,        #     Usage Page (Generic Desktop)
    0x09, 0x30,        #     Usage (X)
    0x09, 0x31,        #     Usage (Y)
    0x15, 0x81,        #     Logical Minimum (-127)
    0x25, 0x7F,        #     Logical Maximum (127)
    0x75, 0x08,        #     Report Size (8)
    0x95, 0x02,        #     Report Count (2)
    0x81, 0x06,        #     Input (Data, Variable, Relative)
    0xC0,              #   End Collection
    0xC0,              # End Collection
])

def create_uhid_device(fd):
    """Create a virtual mouse device"""
    print("Creating UHID device...")

    name = b"Test BLE Mouse\x00"
    name = name.ljust(128, b'\x00')
    phys = b"test:ble-mouse\x00".ljust(64, b'\x00')
    uniq = b'\x00' * 64

    rd_size = len(MOUSE_REPORT_DESCRIPTOR)
    bus = 0x05  # BUS_BLUETOOTH

    # Build CREATE2 event
    create_req = struct.pack('<I', UHID_CREATE2)
    create_req += name
    create_req += phys
    create_req += uniq
    create_req += struct.pack('<HHIII',
        rd_size,  # rd_size
        bus,      # bus
        0x1234,   # vendor
        0x5678,   # product
        0x0001,   # version
    )
    create_req += struct.pack('<I', 0)  # country
    create_req += MOUSE_REPORT_DESCRIPTOR.ljust(4096, b'\x00')

    try:
        os.write(fd, create_req)
        print("SUCCESS: UHID device created!")
        print("\nNow check /dev/input/ for a new eventX device:")
        print("  ls -l /dev/input/")
        print("\nOr check /proc/bus/input/devices for 'Test BLE Mouse'")
        return True
    except OSError as e:
        print(f"FAILED: {e}")
        return False

def send_mouse_movement(fd, dx, dy):
    """Send a mouse movement report"""
    # Mouse report: [buttons, x, y]
    report = bytes([0x00, dx & 0xff, dy & 0xff])

    event = struct.pack('<I', UHID_INPUT2)
    event += struct.pack('<H', len(report))
    event += report.ljust(4096, b'\x00')

    try:
        os.write(fd, event)
        print(f"Sent mouse movement: dx={dx}, dy={dy}")
        return True
    except OSError as e:
        print(f"Failed to send input: {e}")
        return False

def destroy_uhid_device(fd):
    """Destroy the UHID device"""
    print("\nDestroying UHID device...")
    event = struct.pack('<I', UHID_DESTROY)
    try:
        os.write(fd, event)
        print("Device destroyed")
    except OSError as e:
        print(f"Error: {e}")

def main():
    print("=" * 60)
    print("UHID Simple Test")
    print("=" * 60)
    print()

    # Open UHID
    try:
        fd = os.open('/dev/uhid', os.O_RDWR | os.O_NONBLOCK)
        print("Opened /dev/uhid")
    except OSError as e:
        print(f"ERROR: Cannot open /dev/uhid: {e}")
        print("\nMake sure you're running as root:")
        print("  su")
        print("  python3 test_uhid_simple.py")
        return

    try:
        # Create device
        if not create_uhid_device(fd):
            return

        print("\nWaiting 2 seconds for kernel to initialize device...")
        time.sleep(2)

        print("\nNow sending test mouse movements...")
        print("Watch with: evtest /dev/input/eventX (where X is your new device)")
        print()

        # Send some test movements
        for i in range(5):
            send_mouse_movement(fd, 10, 10)
            time.sleep(1)

        print("\nTest complete! If you saw movements in evtest, UHID is working!")
        print("If not, there may be a kernel issue with UHID support.")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        destroy_uhid_device(fd)
        os.close(fd)
        print("Done!")

if __name__ == '__main__':
    main()
