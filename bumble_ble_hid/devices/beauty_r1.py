#!/usr/bin/env python3
"""
BEAUTY-R1 Button Mapper

Button mapper for the BEAUTY-R1 Bluetooth page turner remote.

Button detection based on captured data:
    0x18 -> UP (brightness up)
    0x30 with x:80 (0x80 = -128) -> LEFT (previous page)
    0x30 with small negative x (0xE8=-24, 0xDE=-34, 0xF2=-14) -> RIGHT or DOWN

The device uses button_state combined with X movement to identify gestures.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

from devices.base import ButtonMapper, ButtonResult

__all__ = ['BeautyR1Mapper']


class BeautyR1Mapper(ButtonMapper):
    """Button mapper for BEAUTY-R1 page turner remote.

    Detection strategy:
    - 0x18 = UP
    - 0x30 with x=0x80 (-128) = LEFT
    - 0x30 with other x values = need to distinguish RIGHT vs DOWN
    """

    @property
    def device_name(self) -> str:
        return "BEAUTY-R1"

    def map(self, button_state: int, x_movement: int = 0, y_movement: int = 0) -> ButtonResult:
        """Map BEAUTY-R1 button state to standardized button code.

        Args:
            button_state: Raw button byte from HID report
            x_movement: X movement byte (0-255, interpreted as signed)
            y_movement: Y movement byte (0-255)

        Returns:
            (button_code, button_name) or (None, None) for noise
        """
        # Convert to signed for analysis
        x_signed = x_movement if x_movement < 128 else x_movement - 256

        # UP: button_state 0x18
        if button_state == 0x18:
            return (0x02, "Up")

        # 0x30 pattern - need to use X to distinguish LEFT/RIGHT/DOWN
        if button_state == 0x30:
            # LEFT: x = 0x80 (-128) - strong negative
            if x_movement == 0x80:
                return (0x01, "Left")

            # For other X values, we need more data to distinguish RIGHT vs DOWN
            # Based on captures: x:e8(-24), x:de(-34), x:f2(-14) appear for both
            # For now, use X magnitude: larger negative = DOWN, smaller = RIGHT
            if x_signed <= -30:  # x:de (-34) or similar
                return (0x08, "Down")
            else:  # x:e8 (-24), x:f2 (-14) etc
                return (0x04, "Right")

        # 0xd0 pattern - also DOWN
        if button_state == 0xd0:
            return (0x08, "Down")

        # 0x0f pattern - RIGHT
        if button_state == 0x0f:
            return (0x04, "Right")

        # Ignore pre-signals (0xf8) and releases (0x00)
        return (None, None)
