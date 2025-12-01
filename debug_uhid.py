#!/usr/bin/env python3
"""
Debug script to monitor UHID and input events in real-time

Run on Kindle to verify that:
1. UHID device is created
2. Input reports are being sent to UHID
3. Input events appear in /dev/input/eventX

Usage:
    python3 debug_uhid.py
"""

import os
import struct
import select
import time

# UHID event types
UHID_CREATE2 = 11
UHID_DESTROY = 1
UHID_INPUT2 = 12
UHID_OUTPUT = 6
UHID_START = 2
UHID_STOP = 3
UHID_OPEN = 4
UHID_CLOSE = 5
UHID_GET_REPORT = 9
UHID_SET_REPORT = 13

UHID_EVENT_NAMES = {
    1: "DESTROY",
    2: "START",
    3: "STOP",
    4: "OPEN",
    5: "CLOSE",
    6: "OUTPUT",
    9: "GET_REPORT",
    11: "CREATE2",
    12: "INPUT2",
    13: "SET_REPORT",
}

def monitor_uhid():
    """Monitor /dev/uhid for events"""
    print("Opening /dev/uhid for monitoring...")

    try:
        fd = os.open('/dev/uhid', os.O_RDWR | os.O_NONBLOCK)
    except OSError as e:
        print(f"ERROR: Cannot open /dev/uhid: {e}")
        print("Make sure you're running as root")
        return

    print("Monitoring /dev/uhid (press Ctrl+C to stop)...")
    print("Waiting for UHID events from ble_hid_daemon...\n")

    poll = select.poll()
    poll.register(fd, select.POLLIN)

    event_count = 0

    try:
        while True:
            events = poll.poll(1000)  # 1 second timeout

            if not events:
                print(".", end="", flush=True)
                continue

            # Read UHID event
            try:
                data = os.read(fd, 4100)  # Max UHID event size
                if len(data) < 4:
                    continue

                # Parse event type
                event_type = struct.unpack('<I', data[:4])[0]
                event_name = UHID_EVENT_NAMES.get(event_type, f"UNKNOWN({event_type})")

                event_count += 1
                timestamp = time.strftime("%H:%M:%S")

                print(f"\n[{timestamp}] Event #{event_count}: {event_name}")

                if event_type == UHID_CREATE2:
                    # Parse device name
                    name = data[4:132].rstrip(b'\x00').decode('utf-8', errors='ignore')
                    print(f"  Device Name: {name}")

                    # Parse VID/PID
                    rd_size = struct.unpack('<H', data[260:262])[0]
                    bus = struct.unpack('<H', data[262:264])[0]
                    vid = struct.unpack('<I', data[264:268])[0]
                    pid = struct.unpack('<I', data[268:272])[0]

                    print(f"  Bus: 0x{bus:02x}, VID: 0x{vid:04x}, PID: 0x{pid:04x}")
                    print(f"  Report Descriptor Size: {rd_size} bytes")
                    print("\n  CHECK: After this event, a new /dev/input/eventX should appear!")
                    print("         Run 'ls -l /dev/input/' to verify")

                elif event_type == UHID_INPUT2:
                    # Parse input report
                    report_size = struct.unpack('<H', data[4:6])[0]
                    report_data = data[6:6+report_size]
                    print(f"  Report Size: {report_size} bytes")
                    print(f"  Report Data: {report_data.hex()}")
                    print("\n  CHECK: This should trigger input events in /dev/input/eventX")
                    print("         Run 'evtest /dev/input/eventX' to verify")

                elif event_type == UHID_START:
                    print("  Kernel started using the device (this is good!)")

                elif event_type == UHID_OPEN:
                    print("  Application opened the device (this is good!)")

                elif event_type == UHID_STOP:
                    print("  Kernel stopped using the device")

                elif event_type == UHID_CLOSE:
                    print("  Application closed the device")

                elif event_type == UHID_DESTROY:
                    print("  Device destroyed")

                elif event_type == UHID_OUTPUT:
                    # Output report from kernel to device
                    report_size = struct.unpack('<H', data[4:6])[0]
                    report_data = data[6:6+report_size]
                    print(f"  Output Report Size: {report_size}")
                    print(f"  Output Report Data: {report_data.hex()}")

            except OSError as e:
                if e.errno == 11:  # EAGAIN
                    continue
                print(f"Error reading UHID: {e}")

    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
    finally:
        os.close(fd)
        print(f"\nTotal events received: {event_count}")

def check_input_devices():
    """List current input devices"""
    print("\nCurrent /dev/input devices:")
    print("-" * 60)

    try:
        with open('/proc/bus/input/devices', 'r') as f:
            content = f.read()

        # Parse and display devices
        devices = content.split('\n\n')
        for device in devices:
            if not device.strip():
                continue

            lines = device.split('\n')
            name = ""
            handlers = ""

            for line in lines:
                if line.startswith('N: Name='):
                    name = line[8:].strip('"')
                elif line.startswith('H: Handlers='):
                    handlers = line[12:]

            if name:
                print(f"  {name}")
                print(f"    Handlers: {handlers}")
                print()
    except FileNotFoundError:
        print("  /proc/bus/input/devices not found")

    print("-" * 60)

if __name__ == '__main__':
    print("=" * 60)
    print("UHID Debug Monitor")
    print("=" * 60)

    check_input_devices()
    print()
    monitor_uhid()
