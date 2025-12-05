#!/usr/bin/env python3
"""
BLE-M3 Button Mapper

The BLE-M3 is a common Bluetooth page turner remote that pretends
to be a mouse. It sends movement data along with button presses,
and the movement patterns help distinguish which button was pressed.

This mapper decodes the BLE-M3's unique encoding scheme into
standardized button codes.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

from devices.base import ButtonMapper, ButtonResult

__all__ = ['BLEM3Mapper']


# Direct button state mappings (no movement analysis needed)
_DIRECT_MAPPINGS = {
    # Left button variants
    0x96: (0x01, "Left"),
    0xc6: (0x01, "Left"),
    0x36: (0x01, "Left"),
    0xe8: (0x01, "Left"),

    # Center/Select button
    0x2c: (0x10, "Center"),

    # Enter/Confirm button
    0xd5: (0x20, "Enter"),

    # Right button alternate encoding
    0xFA: (0x04, "Right"),
}


class BLEM3Mapper(ButtonMapper):
    """Button mapper for BLE-M3 page turner remote.

    The BLE-M3 sends HID reports that look like mouse data:
    - Byte 0: Report ID
    - Byte 1: Button state (various encoded values)
    - Byte 2: X movement (signed, used for direction detection)
    - Byte 3: Y movement (signed, used for direction detection)

    The device uses a weird encoding where directional buttons
    (Up/Down/Right) all send button_state=0x68 but with different
    X/Y movement patterns.
    """

    @property
    def device_name(self) -> str:
        return "BLE-M3"

    def map(self, button_state: int, x_movement: int = 0, y_movement: int = 0) -> ButtonResult:
        """Map BLE-M3 button state to standardized button code.

        Args:
            button_state: Raw button byte from HID report
            x_movement: X movement byte (0-255, treat >127 as negative)
            y_movement: Y movement byte (0-255, treat >127 as negative)

        Returns:
            (button_code, button_name) or (None, None) for noise
        """
        # Check direct mappings first (fastest path)
        if button_state in _DIRECT_MAPPINGS:
            return _DIRECT_MAPPINGS[button_state]

        # Handle 0x68 pattern - requires movement analysis
        if button_state == 0x68:
            return self._map_0x68_pattern(x_movement, y_movement)

        # Fallback: treat first set bit as button number
        for i in range(8):
            if button_state & (1 << i):
                return (1 << i, f"Button (bit {i})")

        # Unknown pattern - treat as noise
        return (None, None)

    def _map_0x68_pattern(self, x_movement: int, y_movement: int) -> ButtonResult:
        """Decode the 0x68 button state using movement patterns.

        The 0x68 state is used for directional buttons, differentiated
        by X/Y movement values:

        - RIGHT: x != 0 with strong negative Y (x:01, y:90)
        - UP:    x == 0 with moderate negative Y (-70 to -50)
        - DOWN:  x == 0 with very negative Y (<-70) or positive Y (>20)

        Args:
            x_movement: Unsigned X byte (convert to signed for analysis)
            y_movement: Unsigned Y byte (convert to signed for analysis)

        Returns:
            (button_code, button_name) or (None, None) for noise
        """
        # Convert unsigned bytes to signed integers
        x_signed = x_movement if x_movement < 128 else x_movement - 256
        y_signed = y_movement if y_movement < 128 else y_movement - 256

        # RIGHT: any non-zero X movement with strong negative Y
        if x_movement != 0x00 and y_signed < -50:
            return (0x04, "Right")

        # For zero X movement, use Y ranges to distinguish UP vs DOWN
        if x_movement == 0x00:
            # DOWN: either very negative (< -70) OR positive (> 20)
            if y_signed < -70 or y_signed > 20:
                return (0x08, "Down")

            # UP: moderately negative (-70 to -50)
            if -70 <= y_signed < -50:
                return (0x02, "Up")

        # Everything else is noise
        return (None, None)
