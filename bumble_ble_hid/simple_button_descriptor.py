#!/usr/bin/env python3
"""
Simple button-only HID descriptor for the clicker device
Just reports button states, ignoring all mouse movement data
"""

# HID Report Descriptor for a simple 8-button device
# Report ID 0x00 and 0x07 both map to the same button layout
BUTTON_REPORT_DESCRIPTOR = bytes([
    # Report ID 0 - 8 buttons
    0x05, 0x09,        # Usage Page (Button)
    0x19, 0x01,        # Usage Minimum (Button 1)
    0x29, 0x08,        # Usage Maximum (Button 8)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x01,        # Report Size (1 bit)
    0x95, 0x08,        # Report Count (8 buttons)
    0x81, 0x02,        # Input (Data, Variable, Absolute)

    # Padding for the rest of the 5-byte report (ignore bytes 2-4)
    0x75, 0x08,        # Report Size (8 bits)
    0x95, 0x04,        # Report Count (4 bytes)
    0x81, 0x01,        # Input (Constant) - padding, ignored
])

def patch_report_descriptor(original_descriptor):
    """
    Replace the complex mouse/keyboard/consumer descriptor with
    a simple button-only descriptor that matches what the clicker sends
    """
    return BUTTON_REPORT_DESCRIPTOR

if __name__ == '__main__':
    print("Button-only HID descriptor:")
    print(BUTTON_REPORT_DESCRIPTOR.hex())
    print(f"\nLength: {len(BUTTON_REPORT_DESCRIPTOR)} bytes")
