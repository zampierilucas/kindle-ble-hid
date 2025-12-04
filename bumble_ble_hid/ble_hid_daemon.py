#!/usr/bin/env python3
"""
BLE HID Daemon - Persistent connection manager

Automatically connects to a configured BLE HID device and maintains
persistent connection with auto-reconnect.

Configuration file: /mnt/us/bumble_ble_hid/devices.conf
Format: Single device address (first non-comment line)

Author: Lucas Zampieri <lzampier@redhat.com>
"""

__version__ = "1.5.0"  # Added connection cycle timeout for sleep recovery

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
CONNECTION_CYCLE_TIMEOUT = 90  # max seconds for entire connection cycle (catches BT sleep hangs)

logger = logging.getLogger(__name__)


class BLEHIDDaemon:
    """Daemon that maintains persistent connection to a BLE HID device"""

    def __init__(self):
        self.device_address = None
        self.running = False
        self.host = None
        self.consecutive_timeouts = 0  # Track consecutive cycle timeouts

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
                # Wrap entire connection cycle with timeout to catch BT hardware sleep hangs
                # When Kindle sleeps, BT hardware may also sleep and not respond to HCI commands
                await asyncio.wait_for(
                    self.host.run(self.device_address),
                    timeout=CONNECTION_CYCLE_TIMEOUT
                )
                logger.info("host.run() returned")

                # If we get here, the connection ended normally (disconnect)
                logger.info("Connection ended, will reconnect")
                self.consecutive_timeouts = 0  # Reset on successful cycle

            except asyncio.TimeoutError:
                self.consecutive_timeouts += 1
                logger.warning(f"Connection cycle timed out after {CONNECTION_CYCLE_TIMEOUT}s "
                              f"(consecutive: {self.consecutive_timeouts})")
                logger.warning("BT hardware may be asleep - forcing transport cleanup")
                # Force cleanup will close /dev/stpbt, which should reset the BT state
                await self._force_cleanup()
                # Longer delay after timeout to give hardware time to recover
                if self.consecutive_timeouts >= 3:
                    logger.warning("Multiple consecutive timeouts - waiting longer for BT recovery")
                    await asyncio.sleep(RECONNECT_DELAY * 2)
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
                self.consecutive_timeouts = 0  # Reset on non-timeout errors

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

    async def _force_cleanup(self):
        """Force cleanup of host and transport, with timeout protection.

        This is used when the BT hardware may be unresponsive (e.g., after sleep).
        We use short timeouts since the hardware may not respond at all.
        """
        if not self.host:
            return

        logger.info("Force cleanup: closing transport...")

        # Try graceful cleanup first with short timeout
        try:
            await asyncio.wait_for(self.host.cleanup(), timeout=5.0)
            logger.info("Force cleanup: graceful cleanup succeeded")
        except asyncio.TimeoutError:
            logger.warning("Force cleanup: graceful cleanup timed out, forcing close")
            # Force close the transport if it exists
            if hasattr(self.host, 'transport') and self.host.transport:
                try:
                    # Close the underlying transport directly
                    await asyncio.wait_for(self.host.transport.close(), timeout=2.0)
                except Exception as e:
                    logger.warning(f"Force cleanup: transport close error: {e}")
        except Exception as e:
            logger.warning(f"Force cleanup: error during cleanup: {e}")

        self.host = None
        logger.info("Force cleanup: complete")

    async def stop(self):
        """Stop the daemon"""
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
