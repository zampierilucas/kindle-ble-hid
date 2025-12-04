#!/usr/bin/env python3
"""
BLE HID Daemon - Persistent connection manager

Automatically connects to a configured BLE HID device and maintains
persistent connection with auto-reconnect.

Configuration file: /mnt/us/bumble_ble_hid/devices.conf
Format: Single device address (first non-comment line)

Author: Lucas Zampieri <lzampier@redhat.com>
"""

__version__ = "1.4.0"  # Simplified single-device daemon

import asyncio
import logging
import os
import signal
import sys

# Add the bumble_ble_hid directory to path
sys.path.insert(0, '/mnt/us/bumble_ble_hid')
from kindle_ble_hid import BLEHIDHost

DEVICES_CONFIG = '/mnt/us/bumble_ble_hid/devices.conf'
TRANSPORT = 'file:/dev/stpbt'
RECONNECT_DELAY = 5  # seconds between reconnection attempts

logger = logging.getLogger(__name__)


class BLEHIDDaemon:
    """Daemon that maintains persistent connection to a BLE HID device"""

    def __init__(self):
        self.device_address = None
        self.running = False
        self.host = None

    def load_device(self):
        """Load device address from config file"""
        if not os.path.exists(DEVICES_CONFIG):
            logger.error(f"Config file not found: {DEVICES_CONFIG}")
            return False

        with open(DEVICES_CONFIG, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.device_address = line
                    logger.info(f"Loaded device: {self.device_address}")
                    return True

        logger.error("No device address found in config")
        return False

    async def run(self):
        """Main daemon loop with auto-reconnect"""
        self.running = True

        if not self.load_device():
            logger.error("Failed to load device configuration")
            return

        logger.info(f"BLE HID Daemon v{__version__}")
        logger.info(f"Device: {self.device_address}")
        logger.info(f"Transport: {TRANSPORT}")

        # Reconnection loop
        while self.running:
            try:
                logger.info("=== Starting new connection attempt ===")
                logger.info("Creating BLE HID host...")
                self.host = BLEHIDHost(TRANSPORT)

                logger.info("Connecting to device...")
                await self.host.run(self.device_address)
                logger.info("host.run() returned")

                # If we get here, the connection ended normally (disconnect)
                logger.info("Connection ended, will reconnect")

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except asyncio.CancelledError:
                logger.info("Task cancelled")
                break
            except FileNotFoundError as e:
                logger.error(f"Transport device not found: {e}")
                logger.info("This usually means /dev/stpbt is not available")
                break
            except Exception as e:
                logger.error(f"Error in connection: {e}")
                logger.exception("Connection error details")

            # Clean up host
            if self.host:
                logger.debug("Cleaning up host...")
                try:
                    await self.host.cleanup()
                    logger.debug("Host cleanup complete")
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
                self.host = None

            if not self.running:
                logger.info("Daemon stopping, exiting reconnection loop")
                break

            # Wait before reconnecting
            logger.info(f"Waiting {RECONNECT_DELAY} seconds before reconnection...")
            await asyncio.sleep(RECONNECT_DELAY)

        logger.info("Daemon stopped")

    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping daemon...")
        self.running = False

        if self.host:
            try:
                await self.host.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up host: {e}")


async def main():
    """Entry point"""
    # Configure logging
    root_logger = logging.getLogger()

    # Remove all existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create file handler
    file_handler = logging.FileHandler('/var/log/ble_hid_daemon.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    # Silence verbose Bumble library logs
    logging.getLogger('bumble').setLevel(logging.WARNING)

    daemon = BLEHIDDaemon()
    shutdown_event = asyncio.Event()

    # Handle signals
    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Run daemon in a task
    daemon_task = asyncio.create_task(daemon.run())

    # Wait for either daemon completion or shutdown signal
    done, pending = await asyncio.wait(
        [daemon_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED
    )

    # If shutdown signal received, stop the daemon
    if shutdown_event.is_set():
        await daemon.stop()
        # Cancel daemon task if still running
        if not daemon_task.done():
            daemon_task.cancel()
            try:
                await daemon_task
            except asyncio.CancelledError:
                pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit
