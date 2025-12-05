#!/usr/bin/env python3
"""
Kindle BLE HID Package

BLE HID device support for Amazon Kindle e-readers using Google Bumble.

Modules:
    config          - Centralized configuration
    logging_utils   - Unified logging with timestamps
    pairing         - SMP pairing delegation
    gatt_cache      - GATT attribute caching
    button_handler  - HID report processing and script execution
    host            - Core BLE HID host implementation
    daemon          - Persistent connection manager
    devices         - Device-specific button mappers

Usage:
    # As CLI tool
    python -m bumble_ble_hid.main

    # As daemon
    python -m bumble_ble_hid.daemon

    # Programmatic use
    from bumble_ble_hid.host import BLEHIDHost
    host = BLEHIDHost()
    await host.run(device_address)
"""

from host import BLEHIDHost, __version__
from config import config
from logging_utils import log
from gatt_cache import GATTCache
from button_handler import ButtonHandler

__all__ = [
    'BLEHIDHost',
    'config',
    'log',
    'GATTCache',
    'ButtonHandler',
    '__version__',
]
