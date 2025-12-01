#!/usr/bin/env python3
"""
Patch HID report descriptor to add button reports for IDs 0 and 7
that the Logitech clicker actually sends
"""

# Simple 8-button descriptor for Report ID 0
# Matches the 5-byte format the device sends: [ID, buttons, x, y, wheel]
REPORT_ID_0_DESCRIPTOR = bytes([
    0x85, 0x00,        # Report ID (0)
    0x05, 0x09,        # Usage Page (Button)
    0x19, 0x01,        # Usage Minimum (Button 1)
    0x29, 0x08,        # Usage Maximum (Button 8)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x01,        # Report Size (1 bit)
    0x95, 0x08,        # Report Count (8 buttons)
    0x81, 0x02,        # Input (Data, Variable, Absolute)

    # Padding for bytes 2-4 (x, y, wheel - ignore)
    0x75, 0x08,        # Report Size (8 bits)
    0x95, 0x04,        # Report Count (4 bytes)
    0x81, 0x01,        # Input (Constant) - padding
])

# Simple 8-button descriptor for Report ID 7
REPORT_ID_7_DESCRIPTOR = bytes([
    0x85, 0x07,        # Report ID (7)
    0x05, 0x09,        # Usage Page (Button)
    0x19, 0x01,        # Usage Minimum (Button 1)
    0x29, 0x08,        # Usage Maximum (Button 8)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x01,        # Report Size (1 bit)
    0x95, 0x08,        # Report Count (8 buttons)
    0x81, 0x02,        # Input (Data, Variable, Absolute)

    # Padding for bytes 2-4 (x, y, wheel - ignore)
    0x75, 0x08,        # Report Size (8 bits)
    0x95, 0x04,        # Report Count (4 bytes)
    0x81, 0x01,        # Input (Constant) - padding
])

def patch_report_descriptor(original_descriptor):
    """
    Prepend button descriptors for IDs 0 and 7 to the original descriptor.
    This allows the kernel to accept the reports the device actually sends.
    """
    # Wrap in a top-level application collection
    patched = bytes([
        0x05, 0x01,        # Usage Page (Generic Desktop)
        0x09, 0x05,        # Usage (Game Pad)
        0xA1, 0x01,        # Collection (Application)
    ])

    # Add our button reports
    patched += REPORT_ID_0_DESCRIPTOR
    patched += REPORT_ID_7_DESCRIPTOR

    # Close collection
    patched += bytes([0xC0])  # End Collection

    # Append original descriptor (for the other reports)
    patched += original_descriptor

    return patched

if __name__ == '__main__':
    # Test with the actual descriptor from the device
    original_hex = "050d0901a10185010922a1020942150025017501950181020932810295068103050126e80375109501550065000930350046e8038102093146e8038102c0c0050c0901a101850209e909ea09e209b509b60a240209cd09300a230209401501250c751095018100c005010906a1018503050719e029e71500250175019508810275089501150025f40507190029f48100c0"
    original = bytes.fromhex(original_hex)

    patched = patch_report_descriptor(original)

    print("Patched descriptor:")
    print(patched.hex())
    print(f"\nOriginal length: {len(original)} bytes")
    print(f"Patched length: {len(patched)} bytes")
