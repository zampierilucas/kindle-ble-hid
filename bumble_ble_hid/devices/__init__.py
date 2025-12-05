#!/usr/bin/env python3
"""
Device-specific button mappers.

Each BLE HID device may send button data in different formats.
This package provides pluggable mappers for different devices.

Supported devices:
- BLE-M3: Common BLE page turner remote
- BEAUTY-R1: Page turner remote (TODO: capture HID data)
"""

from typing import Optional

from devices.base import ButtonMapper
from devices.ble_m3 import BLEM3Mapper
from devices.beauty_r1 import BeautyR1Mapper

__all__ = ['ButtonMapper', 'BLEM3Mapper', 'BeautyR1Mapper', 'get_mapper_for_device']

# Registry mapping device name patterns to mapper classes
# Keys are substrings that will be matched against the BLE device name (case-insensitive)
_DEVICE_REGISTRY = {
    'ble-m3': BLEM3Mapper,
    'm3': BLEM3Mapper,
    'beauty-r1': BeautyR1Mapper,
    'beauty': BeautyR1Mapper,
    'r1': BeautyR1Mapper,
}


def get_mapper_for_device(device_name: Optional[str]) -> ButtonMapper:
    """Get the appropriate button mapper for a device.

    Args:
        device_name: BLE device name (e.g., "BLE-M3", "BEAUTY-R1")

    Returns:
        ButtonMapper instance for the device, or BLEM3Mapper as default
    """
    if device_name:
        name_lower = device_name.lower()
        for pattern, mapper_class in _DEVICE_REGISTRY.items():
            if pattern in name_lower:
                return mapper_class()

    # Default to BLE-M3 mapper
    return BLEM3Mapper()
