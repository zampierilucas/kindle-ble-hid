#!/usr/bin/env python3
"""
Kindle BLE HID - Main Entry Point

Command-line interface for the BLE HID host.
For daemon mode, use daemon.py instead.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

import argparse
import asyncio
import os
import sys

# Add the bumble_ble_hid directory to path for Kindle deployment
sys.path.insert(0, '/mnt/us/bumble_ble_hid')

from config import config
from logging_utils import log, setup_logging
from host import BLEHIDHost, __version__


async def main():
    parser = argparse.ArgumentParser(
        description='Kindle BLE HID Host using Google Bumble'
    )
    parser.add_argument(
        '-t', '--transport',
        default=config.transport,
        help=f'HCI transport specification (default: {config.transport})'
    )
    parser.add_argument(
        '-a', '--address',
        help='Target BLE device address (if not specified, will scan)'
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--scan-only',
        action='store_true',
        help='Scan for devices and exit'
    )
    parser.add_argument(
        '--scan-duration',
        type=int,
        default=30,
        help='Duration to scan for devices in seconds (default: 30)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    args = parser.parse_args()

    # Configure logging
    setup_logging(debug=args.debug)

    # Handle scan-only mode
    if args.scan_only:
        log.info("Scanning for BLE devices...")
        host = BLEHIDHost(args.transport)

        try:
            await host.start()
            devices = await host.scan(duration=args.scan_duration, filter_hid=False)

            if devices:
                log.success(f"\nFound {len(devices)} BLE device(s):")
                for dev in devices:
                    log.raw(f"  {dev['name']:30s} {dev['address']}")
            else:
                log.warning("\nNo BLE devices found")
                log.warning("Make sure your device is in pairing mode")

            await host.cleanup()
        except Exception as e:
            log.error(f"Error during scan: {e}")

        return

    # Load device address from config if not specified
    target_address = args.address
    if not target_address:
        target_address = config.get_device_address()
        if target_address:
            log.info(f"Using device from devices.conf: {target_address}")

    # Create and run the HID host
    host = BLEHIDHost(args.transport)
    await host.run(target_address)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C
