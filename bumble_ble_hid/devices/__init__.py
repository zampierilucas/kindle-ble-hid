#!/usr/bin/env python3
"""
Device-specific button mappers.

Each BLE HID device may send button data in different formats.
This package provides pluggable mappers for different devices.

Supported devices:
- BLE-M3: Common BLE page turner remote
"""

from devices.base import ButtonMapper
from devices.ble_m3 import BLEM3Mapper

__all__ = ['ButtonMapper', 'BLEM3Mapper']
