#!/usr/bin/env python3
"""
Decode HID Report Descriptor to understand device structure
"""

descriptor_hex = "050d0901a10185010922a1020942150025017501950181020932810295068103050126e80375109501550065000930350046e8038102093146e8038102c0c0050c0901a101850209e909ea09e209b509b60a240209cd09300a230209401501250c751095018100c005010906a1018503050719e029e71500250175019508810275089501150025f40507190029f48100c0"

descriptor = bytes.fromhex(descriptor_hex)

# Basic HID descriptor parser
i = 0
indent = 0

print("HID Report Descriptor Decode:")
print("=" * 60)

while i < len(descriptor):
    b = descriptor[i]

    # Get item size
    size = b & 0x03
    if size == 3:
        size = 4

    # Get item type and tag
    item_type = (b >> 2) & 0x03
    tag = (b >> 4) & 0x0F

    # Get data
    data = 0
    if size > 0:
        for j in range(size):
            if i + 1 + j < len(descriptor):
                data |= descriptor[i + 1 + j] << (j * 8)

    prefix = "  " * indent

    # Decode based on type and tag
    if item_type == 0:  # Main items
        if tag == 0x08:  # Input
            print(f"{prefix}Input ({hex(data)})")
        elif tag == 0x09:  # Output
            print(f"{prefix}Output ({hex(data)})")
        elif tag == 0x0A:  # Collection
            coll_types = {0: "Physical", 1: "Application", 2: "Logical"}
            print(f"{prefix}Collection ({coll_types.get(data, data)})")
            indent += 1
        elif tag == 0x0C:  # End Collection
            indent -= 1
            print(f"{prefix}End Collection")

    elif item_type == 1:  # Global items
        if tag == 0x00:  # Usage Page
            pages = {
                0x01: "Generic Desktop",
                0x05: "Game Controls",
                0x07: "Keyboard",
                0x0C: "Consumer",
                0x0D: "Digitizer"
            }
            print(f"{prefix}Usage Page ({pages.get(data, hex(data))})")
        elif tag == 0x01:  # Logical Minimum
            if data > 127:
                data = data - 256
            print(f"{prefix}Logical Minimum ({data})")
        elif tag == 0x02:  # Logical Maximum
            print(f"{prefix}Logical Maximum ({data})")
        elif tag == 0x05:  # Unit Exponent
            print(f"{prefix}Unit Exponent ({data})")
        elif tag == 0x06:  # Unit
            print(f"{prefix}Unit ({data})")
        elif tag == 0x07:  # Report Size
            print(f"{prefix}Report Size ({data} bits)")
        elif tag == 0x08:  # Report ID
            print(f"{prefix}*** Report ID {data} ***")
        elif tag == 0x09:  # Report Count
            print(f"{prefix}Report Count ({data})")
        elif tag == 0x03:  # Physical Minimum
            print(f"{prefix}Physical Minimum ({data})")
        elif tag == 0x04:  # Physical Maximum
            print(f"{prefix}Physical Maximum ({data})")

    elif item_type == 2:  # Local items
        if tag == 0x00:  # Usage
            usages = {
                0x01: "Pointer",
                0x02: "Mouse",
                0x06: "Keyboard",
                0x30: "X",
                0x31: "Y",
                0x32: "Z",
                0x42: "Tip Switch",
                0xe0: "Left Control",
                0xe7: "Right GUI"
            }
            print(f"{prefix}Usage ({usages.get(data, hex(data))})")
        elif tag == 0x01:  # Usage Minimum
            print(f"{prefix}Usage Minimum ({hex(data)})")
        elif tag == 0x02:  # Usage Maximum
            print(f"{prefix}Usage Maximum ({hex(data)})")

    i += 1 + size

print("=" * 60)
