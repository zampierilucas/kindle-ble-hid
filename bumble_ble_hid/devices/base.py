#!/usr/bin/env python3
"""
Abstract Base Class for Button Mappers

Defines the interface for device-specific button mapping.
Each BLE HID device may encode button presses differently.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

__all__ = ['ButtonMapper', 'ButtonResult']

# Type alias for button mapping result
# (button_code, button_name) or (None, None) for unrecognized input
ButtonResult = Tuple[Optional[int], Optional[str]]


class ButtonMapper(ABC):
    """Abstract base class for device-specific button mapping.

    Implementations translate raw HID report data into
    standardized button codes that can be mapped to scripts.

    Standard button codes:
        0x01 - Button 1 (typically Left/Previous)
        0x02 - Button 2 (typically Up/Brightness+)
        0x04 - Button 3 (typically Right/Next)
        0x08 - Button 4 (typically Down/Brightness-)
        0x10 - Button 5 (typically Center/Select)
        0x20 - Button 6 (typically Enter/Confirm)
    """

    @abstractmethod
    def map(self, button_state: int, x_movement: int = 0,
            y_movement: int = 0) -> ButtonResult:
        """Map raw HID data to a standardized button code.

        Args:
            button_state: Raw button byte from HID report
            x_movement: X movement byte (for mouse-like devices)
            y_movement: Y movement byte (for mouse-like devices)

        Returns:
            Tuple of (button_code, button_name) if recognized,
            or (None, None) if the input should be ignored.
        """
        pass

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Human-readable name of the device this mapper supports."""
        pass

    def is_release_event(self, button_state: int) -> bool:
        """Check if this is a button release event.

        Default implementation treats button_state == 0 as release.
        Override for devices with different release detection.

        Args:
            button_state: Raw button byte from HID report

        Returns:
            True if this is a release event (should be ignored)
        """
        return button_state == 0
