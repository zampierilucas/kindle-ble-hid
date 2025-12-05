#!/usr/bin/env python3
"""
BLE HID Daemon - Persistent connection manager

Automatically connects to configured BLE HID devices and maintains
persistent connection with auto-reconnect.

Configuration file: /mnt/us/bumble_ble_hid/devices.conf
Format: One MAC address per line (comments start with #)
        Tries each device in order until one connects.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

__version__ = "2.0.0"  # Refactored modular architecture

import asyncio
import logging
import signal
import sys

# Add the bumble_ble_hid directory to path for Kindle deployment
sys.path.insert(0, '/mnt/us/bumble_ble_hid')

from config import config
from logging_utils import setup_daemon_logging
from host import BLEHIDHost

__all__ = ['BLEHIDDaemon', '__version__']

logger = logging.getLogger(__name__)


class BLEHIDDaemon:
    """Daemon that maintains persistent connection to BLE HID devices.

    Features:
    - Multiple device support (tries each until one connects)
    - Auto-reconnect on disconnection
    - Connection cycle timeout for hardware sleep recovery
    - Exponential backoff on repeated timeouts
    - Graceful shutdown handling
    """

    def __init__(self):
        self.device_addresses = []
        self.current_device_index = 0
        self.running = False
        self.host = None
        self.consecutive_timeouts = 0

    def load_devices(self) -> bool:
        """Load device addresses from config file.

        Returns:
            True if at least one device address loaded successfully
        """
        self.device_addresses = config.get_device_addresses()

        if not self.device_addresses:
            logger.error(f"No device addresses found in {config.devices_config_file}")
            return False

        logger.info(f"Loaded {len(self.device_addresses)} device(s):")
        for i, addr in enumerate(self.device_addresses):
            logger.info(f"  [{i+1}] {addr}")
        return True

    def get_next_device(self) -> str:
        """Get the next device address to try (round-robin)."""
        addr = self.device_addresses[self.current_device_index]
        self.current_device_index = (self.current_device_index + 1) % len(self.device_addresses)
        return addr

    async def run(self):
        """Main daemon loop with auto-reconnect."""
        self.running = True

        if not self.load_devices():
            logger.error("Failed to load device configuration")
            return

        logger.info(f"BLE HID Daemon v{__version__}")
        logger.info(f"Transport: {config.transport}")

        # Reconnection loop
        while self.running:
            device_address = self.get_next_device()
            try:
                logger.info("=== Starting new connection attempt ===")
                logger.info(f"Target device: {device_address}")
                logger.info("Creating BLE HID host...")
                self.host = BLEHIDHost(config.transport)

                logger.info("Connecting to device...")
                # Wrap entire connection cycle with timeout
                await asyncio.wait_for(self.host.run(device_address), timeout=config.cycle_timeout)
                logger.info("host.run() returned")

                # Connection ended normally
                logger.info("Connection ended, will reconnect")
                self.consecutive_timeouts = 0

            except asyncio.TimeoutError:
                self.consecutive_timeouts += 1
                logger.warning(f"Connection cycle timed out after {config.cycle_timeout}s (consecutive: {self.consecutive_timeouts})")
                logger.warning("BT hardware may be asleep - forcing transport cleanup")
                await self._force_cleanup()

                # Extended delay after multiple timeouts
                if self.consecutive_timeouts >= 3:
                    logger.warning("Multiple consecutive timeouts - waiting longer")
                    await asyncio.sleep(config.reconnect_delay * 2)

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
                self.consecutive_timeouts = 0

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
            logger.info(f"Waiting {config.reconnect_delay} seconds before reconnection...")
            await asyncio.sleep(config.reconnect_delay)

        logger.info("Daemon stopped")

    async def _force_cleanup(self):
        """Force cleanup of host and transport with timeout protection."""
        if not self.host:
            return

        logger.info("Force cleanup: closing transport...")

        try:
            await asyncio.wait_for(self.host.cleanup(), timeout=5.0)
            logger.info("Force cleanup: graceful cleanup succeeded")
        except asyncio.TimeoutError:
            logger.warning("Force cleanup: graceful cleanup timed out, forcing close")
            if hasattr(self.host, 'transport') and self.host.transport:
                try:
                    await asyncio.wait_for(self.host.transport.close(), timeout=2.0)
                except Exception as e:
                    logger.warning(f"Force cleanup: transport close error: {e}")
        except Exception as e:
            logger.warning(f"Force cleanup: error during cleanup: {e}")

        self.host = None
        logger.info("Force cleanup: complete")

    async def stop(self):
        """Stop the daemon."""
        logger.info("Stopping daemon...")
        self.running = False

        if self.host:
            try:
                await asyncio.wait_for(self.host.cleanup(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Stop: cleanup timed out")
            except Exception as e:
                logger.error(f"Error cleaning up host: {e}")


async def main():
    """Entry point."""
    # Configure logging for daemon mode
    setup_daemon_logging(config.log_file)

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
