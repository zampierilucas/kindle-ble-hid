#!/usr/bin/env python3
"""
BLE HID Daemon - Persistent connection manager

Automatically connects to configured BLE HID devices and maintains
persistent connections with auto-reconnect.

Configuration file: /mnt/us/bumble_ble_hid/devices.conf
Format: One device address per line

Author: Lucas Zampieri <lzampier@redhat.com>
"""

import asyncio
import logging
import os
import signal
import sys
import time

# Add the bumble_ble_hid directory to path
sys.path.insert(0, '/mnt/us/bumble_ble_hid')
from kindle_ble_hid import BLEHIDHost

DEVICES_CONFIG = '/mnt/us/bumble_ble_hid/devices.conf'
TRANSPORT = 'file:/dev/stpbt'
RECONNECT_DELAY_ACTIVE = 3  # seconds - fast retry when Kindle is active
RECONNECT_DELAY_IDLE = 30  # seconds - slow retry when Kindle is idle
CONNECTION_TIMEOUT = 10  # seconds - shorter timeout to save battery
IDLE_THRESHOLD = 60  # seconds - consider idle after 60s of no input events

logger = logging.getLogger(__name__)


class BLEHIDDaemon:
    """Daemon that maintains persistent connections to BLE HID devices"""

    def __init__(self):
        self.devices = []
        self.running = False
        self.tasks = []
        self.host = None
        self.connections = {}  # address -> connection info
        self.disconnect_event = None  # Event to signal disconnection
        self.last_activity_time = time.time()  # Track last user activity

    def load_devices(self):
        """Load device addresses from config file"""
        if not os.path.exists(DEVICES_CONFIG):
            logger.warning(f"Config file not found: {DEVICES_CONFIG}")
            return

        with open(DEVICES_CONFIG, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.devices.append(line)

        logger.info(f"Loaded {len(self.devices)} device(s) from config")

    def is_kindle_active(self):
        """Check if Kindle has recent user activity"""
        # Check if there's been activity in the last IDLE_THRESHOLD seconds
        time_since_activity = time.time() - self.last_activity_time
        return time_since_activity < IDLE_THRESHOLD

    async def monitor_activity(self):
        """Monitor input events to detect user activity"""
        try:
            # Monitor /dev/input/event* for any input activity
            import glob
            event_devices = glob.glob('/dev/input/event*')

            if not event_devices:
                logger.warning("No input devices found, using time-based activity")
                return

            # Use select to monitor all input devices
            import select
            fds = []
            for device in event_devices:
                try:
                    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
                    fds.append(fd)
                except:
                    pass

            if not fds:
                logger.warning("Could not open input devices, using time-based activity")
                return

            logger.info(f"Monitoring {len(fds)} input devices for activity")

            while self.running:
                # Use select with timeout to check for input events
                readable, _, _ = select.select(fds, [], [], 1.0)

                if readable:
                    # Activity detected, update timestamp
                    self.last_activity_time = time.time()
                    # Drain the events
                    for fd in readable:
                        try:
                            os.read(fd, 4096)
                        except:
                            pass

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"Error monitoring activity: {e}")
        finally:
            # Clean up file descriptors
            for fd in fds:
                try:
                    os.close(fd)
                except:
                    pass

    async def connect_device(self, address):
        """Connect to a device with auto-reconnect based on Kindle activity"""
        while self.running:
            try:
                logger.info(f"Connecting to {address}...")

                # Create disconnect event for this connection
                self.disconnect_event = asyncio.Event()

                # Connect to device with shorter timeout
                try:
                    await self.host.connect(address, timeout=CONNECTION_TIMEOUT)
                    logger.info(f"Connected to {address}")
                except AssertionError as ae:
                    # Handle Bumble's assertion error when own_address_type is None
                    # This can happen after forcible device restart during reconnection
                    if "own_address_type" in str(ae):
                        logger.error(f"Bumble address type assertion error - controller state issue: {ae}")
                        logger.info("Recreating Bumble host to reset state...")

                        # Clean up current host
                        try:
                            await self.host.cleanup()
                        except Exception:
                            pass

                        # Recreate host with fresh state
                        from kindle_ble_hid import BLEHIDHost
                        self.host = BLEHIDHost(TRANSPORT)
                        await self.host.start()
                        logger.info("Host recreated, will retry connection")
                        raise TimeoutError("Host reset needed")
                    else:
                        # Re-raise other assertion errors
                        raise

                # Set up disconnection callback
                def on_disconnect(reason):
                    logger.warning(f"Disconnected from {address}: reason={reason}")
                    self.disconnect_event.set()

                if self.host.connection:
                    self.host.connection.on('disconnection', on_disconnect)

                # Pair
                logger.info(f"Pairing with {address}...")
                await self.host.pair()
                logger.info(f"Paired with {address}")

                # Discover HID service
                logger.info(f"Discovering HID service on {address}...")
                if await self.host.discover_hid_service():
                    logger.info(f"Creating UHID device for {address}...")
                    uhid_created = await self.host.create_uhid_device(f"BLE HID {address}")
                    if not uhid_created:
                        logger.error(f"Failed to create UHID device for {address}")
                        raise Exception("UHID device creation failed")

                    # Now subscribe to HID reports (AFTER UHID device is created)
                    logger.info(f"Subscribing to HID reports from {address}...")
                    await self.host.subscribe_to_reports()

                    logger.info(f"Successfully connected to {address}")

                    # Store connection info
                    self.connections[address] = {
                        'connection': self.host.connection,
                        'uhid': self.host.uhid_device
                    }

                    # Wait for disconnection using event
                    logger.info(f"Monitoring connection to {address}...")
                    await self.disconnect_event.wait()

                    logger.warning(f"Disconnected from {address}")
                else:
                    logger.error(f"Failed to discover HID service on {address}")

            except KeyboardInterrupt:
                raise
            except TimeoutError:
                logger.debug(f"Connection timeout to {address}")
            except Exception as e:
                logger.error(f"Error connecting to {address}: {e}")

            # Clean up connection
            if address in self.connections:
                try:
                    if self.connections[address].get('uhid'):
                        self.connections[address]['uhid'].destroy()
                except:
                    pass
                del self.connections[address]

            if not self.running:
                break

            # Use activity-based reconnect delay
            if self.is_kindle_active():
                delay = RECONNECT_DELAY_ACTIVE
                status = "active"
            else:
                delay = RECONNECT_DELAY_IDLE
                status = "idle"

            logger.info(f"Kindle is {status}, reconnecting to {address} in {delay} seconds...")
            await asyncio.sleep(delay)

    async def run(self):
        """Main daemon loop"""
        self.running = True
        self.load_devices()

        if not self.devices:
            logger.error("No devices configured. Add device addresses to devices.conf")
            return

        try:
            # Create single Bumble host instance
            logger.info("Initializing Bumble BLE host...")
            self.host = BLEHIDHost(TRANSPORT)
            await self.host.start()
            logger.info("Bumble BLE host started")

            # Start activity monitoring in background
            activity_task = asyncio.create_task(self.monitor_activity())

            # NOTE: For now, only support ONE device at a time
            # Bumble can handle multiple connections, but our current
            # BLEHIDHost implementation is designed for single device use
            if len(self.devices) > 1:
                logger.warning(f"Multiple devices configured ({len(self.devices)}), but only connecting to first one")
                logger.warning("Multi-device support requires code changes")

            # Connect to first device only
            await self.connect_device(self.devices[0])

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the daemon and clean up"""
        logger.info("Stopping daemon...")
        self.running = False

        # Clean up all connections
        for address, conn_info in list(self.connections.items()):
            try:
                if conn_info.get('uhid'):
                    conn_info['uhid'].destroy()
            except:
                pass

        # Clean up host
        if self.host:
            try:
                await self.host.cleanup()
            except:
                pass

        logger.info("Daemon stopped")


async def main():
    """Entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[
            logging.FileHandler('/var/log/ble_hid_daemon.log'),
            logging.StreamHandler()
        ]
    )

    daemon = BLEHIDDaemon()
    shutdown_event = asyncio.Event()

    # Handle signals
    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Run daemon in a task so we can cancel it
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
