#!/usr/bin/env python3
"""
Kindle BLE HID Host using Google Bumble

This implements a BLE HID host that:
1. Connects to /dev/stpbt (MediaTek STP Bluetooth)
2. Scans for and connects to BLE HID devices
3. Handles SMP pairing (bypassing kernel SMP bug)
4. Parses HID over GATT (HOGP) reports
5. Injects input events via /dev/uhid

Author: Lucas Zampieri <lzampier@redhat.com>
Date: December 2025
"""

import asyncio
import argparse
import logging
import os
import struct
import sys

from bumble.device import Device, Peer
from bumble.hci import Address
from bumble.gatt import (
    GATT_GENERIC_ACCESS_SERVICE,
    GATT_DEVICE_NAME_CHARACTERISTIC,
)
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.transport import open_transport
from bumble.core import UUID, AdvertisingData
from bumble.colors import color

# -----------------------------------------------------------------------------
# BLE HID Service UUIDs (from Bluetooth SIG)
# -----------------------------------------------------------------------------
GATT_HID_SERVICE = UUID.from_16_bits(0x1812)
GATT_HID_INFORMATION_CHARACTERISTIC = UUID.from_16_bits(0x2A4A)
GATT_HID_REPORT_MAP_CHARACTERISTIC = UUID.from_16_bits(0x2A4B)
GATT_HID_CONTROL_POINT_CHARACTERISTIC = UUID.from_16_bits(0x2A4C)
GATT_HID_REPORT_CHARACTERISTIC = UUID.from_16_bits(0x2A4D)
GATT_HID_PROTOCOL_MODE_CHARACTERISTIC = UUID.from_16_bits(0x2A4E)

# Report Reference Descriptor
GATT_REPORT_REFERENCE_DESCRIPTOR = UUID.from_16_bits(0x2908)
# Client Characteristic Configuration Descriptor
GATT_CCCD = UUID.from_16_bits(0x2902)

# Battery Service
GATT_BATTERY_SERVICE = UUID.from_16_bits(0x180F)
GATT_BATTERY_LEVEL_CHARACTERISTIC = UUID.from_16_bits(0x2A19)

# Device Information Service
GATT_DEVICE_INFORMATION_SERVICE = UUID.from_16_bits(0x180A)

# HID Report Types
HID_REPORT_TYPE_INPUT = 1
HID_REPORT_TYPE_OUTPUT = 2
HID_REPORT_TYPE_FEATURE = 3

# -----------------------------------------------------------------------------
# UHID Interface for Linux Input Injection
# -----------------------------------------------------------------------------
UHID_DEVICE = '/dev/uhid'

# UHID event types
UHID_CREATE2 = 11
UHID_DESTROY = 1
UHID_INPUT2 = 12
UHID_OUTPUT = 6
UHID_START = 2
UHID_STOP = 3
UHID_OPEN = 4
UHID_CLOSE = 5

class UHIDDevice:
    """Interface to /dev/uhid for creating virtual HID devices"""

    def __init__(self, name: str, vid: int, pid: int, report_descriptor: bytes):
        self.name = name
        self.vid = vid
        self.pid = pid
        self.report_descriptor = report_descriptor
        self.fd = None
        self.running = False

    async def create(self):
        """Create the UHID device"""
        try:
            self.fd = os.open(UHID_DEVICE, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            logging.error(f"Failed to open {UHID_DEVICE}: {e}")
            logging.error("Make sure you have permissions (run as root or add to input group)")
            return False

        # Build UHID_CREATE2 event
        # struct uhid_create2_req {
        #     __u8 name[128];
        #     __u8 phys[64];
        #     __u8 uniq[64];
        #     __u16 rd_size;
        #     __u16 bus;
        #     __u32 vendor;
        #     __u32 product;
        #     __u32 version;
        #     __u32 country;
        #     __u8 rd_data[HID_MAX_DESCRIPTOR_SIZE]; /* 4096 */
        # }

        name_bytes = self.name.encode('utf-8')[:127] + b'\x00'
        name_bytes = name_bytes.ljust(128, b'\x00')

        phys = b'bumble:ble-hid\x00'.ljust(64, b'\x00')
        uniq = b'\x00' * 64

        rd_size = len(self.report_descriptor)
        bus = 0x05  # BUS_BLUETOOTH

        # Pack the create2 request
        create_req = struct.pack(
            '<I',  # event type
            UHID_CREATE2
        )
        create_req += name_bytes
        create_req += phys
        create_req += uniq
        create_req += struct.pack('<HHIII',
            rd_size,
            bus,
            self.vid,
            self.pid,
            0x0001,  # version
        )
        create_req += struct.pack('<I', 0)  # country
        create_req += self.report_descriptor.ljust(4096, b'\x00')

        try:
            os.write(self.fd, create_req)
            self.running = True
            logging.info(f"Created UHID device: {self.name}")
            return True
        except OSError as e:
            logging.error(f"Failed to create UHID device: {e}")
            return False

    def send_input(self, report_data: bytes):
        """Send an input report to the virtual HID device"""
        if not self.running:
            logging.error(f"UHID send_input: device not running (running={self.running})")
            return
        if self.fd is None:
            logging.error(f"UHID send_input: fd is None")
            return

        # struct uhid_input2_req {
        #     __u16 size;
        #     __u8 data[UHID_DATA_MAX]; /* 4096 */
        # }

        event = struct.pack('<I', UHID_INPUT2)
        event += struct.pack('<H', len(report_data))
        event += report_data.ljust(4096, b'\x00')

        try:
            bytes_written = os.write(self.fd, event)
            print(color(f"    UHID: Sent {bytes_written} bytes (fd={self.fd}, expected={len(event)})", 'blue'))
            if bytes_written != len(event):
                logging.error(f"Partial write! Expected {len(event)}, wrote {bytes_written}")
        except OSError as e:
            logging.error(f"Failed to send input report: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in send_input: {e}")

    def destroy(self):
        """Destroy the UHID device"""
        if self.fd is not None:
            if self.running:
                event = struct.pack('<I', UHID_DESTROY)
                try:
                    os.write(self.fd, event)
                except OSError:
                    pass
                self.running = False
            os.close(self.fd)
            self.fd = None
            logging.info("Destroyed UHID device")


# -----------------------------------------------------------------------------
# Pairing Delegate for user interaction
# -----------------------------------------------------------------------------
class SimplePairingDelegate(PairingDelegate):
    """Simple pairing delegate that accepts all pairings with display capability"""

    def __init__(self, io_capability=PairingDelegate.DISPLAY_OUTPUT_AND_YES_NO_INPUT):
        super().__init__(io_capability=io_capability)

    async def accept(self):
        print(color(">>> Pairing request received - accepting", 'green'))
        return True

    async def compare_numbers(self, number, digits):
        print(color(f">>> Confirm number: {number:0{digits}}", 'yellow'))
        print(color(">>> Auto-accepting (press Ctrl+C to cancel)", 'yellow'))
        return True

    async def get_number(self):
        print(color(">>> Enter PIN (or 0 for default): ", 'yellow'))
        return 0

    async def display_number(self, number, digits):
        print(color(f">>> Display PIN: {number:0{digits}}", 'cyan'))


# -----------------------------------------------------------------------------
# BLE HID Host Implementation
# -----------------------------------------------------------------------------
class BLEHIDHost:
    """BLE HID Host that connects to HID devices and injects input"""

    def __init__(self, transport_spec: str, device_config: str = None):
        self.transport_spec = transport_spec
        self.device_config = device_config
        self.device = None
        self.connection = None
        self.peer = None
        self.uhid_device = None
        self.hid_reports = {}  # report_id -> characteristic
        self.report_map = None

    async def start(self):
        """Initialize the Bumble device"""
        print(color(">>> Opening transport...", 'blue'))
        self.transport = await open_transport(self.transport_spec)

        if self.device_config:
            self.device = Device.from_config_file_with_hci(
                self.device_config,
                self.transport.source,
                self.transport.sink
            )
        else:
            self.device = Device.with_hci(
                'Kindle-BLE-HID',
                'F0:F0:F0:F0:F0:F0',
                self.transport.source,
                self.transport.sink
            )

        # Configure pairing
        self.device.pairing_config_factory = lambda connection: PairingConfig(
            sc=True,  # Secure Connections
            mitm=True,  # MITM protection
            bonding=True,  # Enable bonding
            delegate=SimplePairingDelegate(),
        )

        await self.device.power_on()
        print(color(f">>> Device powered on: {self.device.public_address}", 'green'))

    async def scan(self, duration: float = 10.0, filter_hid: bool = True):
        """Scan for BLE devices, optionally filtering for HID devices"""
        print(color(f">>> Scanning for {duration} seconds...", 'blue'))

        devices_found = []
        seen_addresses = set()

        def on_advertisement(advertisement):
            addr_str = str(advertisement.address)

            # Skip duplicates
            if addr_str in seen_addresses:
                return
            seen_addresses.add(addr_str)

            # Extract device name from advertising data using get() method
            name = 'Unknown'
            if hasattr(advertisement, 'data') and advertisement.data:
                # Try complete local name first, then shortened
                name = advertisement.data.get(AdvertisingData.COMPLETE_LOCAL_NAME)
                if not name:
                    name = advertisement.data.get(AdvertisingData.SHORTENED_LOCAL_NAME)
                if not name:
                    name = 'Unknown'
                # Decode if bytes
                if isinstance(name, bytes):
                    name = name.decode('utf-8', errors='replace')

            # Check for HID service UUID in advertisement using get() method
            is_hid = False
            if hasattr(advertisement, 'data') and advertisement.data:
                # Get list of service UUIDs
                services = advertisement.data.get(AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS)
                if not services:
                    services = advertisement.data.get(AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS)

                # Check if HID service UUID is present
                if services:
                    for service_uuid in services:
                        # service_uuid is a UUID object, compare with HID service UUID
                        if service_uuid == GATT_HID_SERVICE:
                            is_hid = True
                            break

            if not filter_hid or is_hid:
                entry = {
                    'address': addr_str,
                    'name': name,
                    'rssi': advertisement.rssi,
                    'is_hid': is_hid,
                }
                devices_found.append(entry)
                hid_marker = " [HID]" if is_hid else ""
                print(color(f"    Found: {entry['name']} ({entry['address']}) RSSI: {entry['rssi']}{hid_marker}", 'cyan'))

        self.device.on('advertisement', on_advertisement)
        await self.device.start_scanning(filter_duplicates=True)
        await asyncio.sleep(duration)
        await self.device.stop_scanning()

        print(color(f">>> Scan complete. Found {len(devices_found)} devices.", 'green'))
        return devices_found

    async def connect(self, address: str, timeout: int = 30):
        """Connect to a BLE device"""
        print(color(f">>> Connecting to {address}...", 'blue'))

        target = Address(address)
        try:
            self.connection = await asyncio.wait_for(
                self.device.connect(target),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Connection timeout after {timeout}s. Is the device powered on and advertising?")

        self.peer = Peer(self.connection)

        print(color(f">>> Connected to {self.connection.peer_address}", 'green'))

        # Set up connection event handlers
        self.connection.on('disconnection', self._on_disconnection)
        self.connection.on('pairing', self._on_pairing)
        self.connection.on('pairing_failure', self._on_pairing_failure)

        return self.connection

    def _on_disconnection(self, reason):
        print(color(f">>> Disconnected: reason={reason}", 'red'))
        if self.uhid_device:
            self.uhid_device.destroy()

    def _on_pairing(self, keys):
        print(color(">>> Pairing successful!", 'green'))

    def _on_pairing_failure(self, reason):
        print(color(f">>> Pairing failed: {reason}", 'red'))

    async def pair(self):
        """Initiate pairing with the connected device"""
        if not self.connection:
            print(color(">>> Not connected!", 'red'))
            return False

        print(color(">>> Initiating pairing...", 'blue'))
        try:
            await self.connection.pair()
            print(color(">>> Pairing complete!", 'green'))
            return True
        except Exception as e:
            print(color(f">>> Pairing error: {e}", 'red'))
            return False

    async def discover_hid_service(self):
        """Discover and subscribe to HID service characteristics"""
        if not self.peer:
            print(color(">>> Not connected!", 'red'))
            return False

        print(color(">>> Discovering GATT services...", 'blue'))

        # Discover all services
        await self.peer.discover_services()

        # Find HID service
        hid_services = [s for s in self.peer.services if s.uuid == GATT_HID_SERVICE]

        if not hid_services:
            print(color(">>> HID service not found!", 'red'))
            return False

        hid_service = hid_services[0]
        print(color(f">>> Found HID service: {hid_service.uuid}", 'green'))

        # Discover characteristics (pass service as named argument)
        await self.peer.discover_characteristics(service=hid_service)

        for char in hid_service.characteristics:
            print(color(f"    Characteristic: {char.uuid}", 'cyan'))

            if char.uuid == GATT_HID_REPORT_MAP_CHARACTERISTIC:
                # Read report map (HID descriptor)
                try:
                    value = await self.peer.read_value(char)
                    self.report_map = bytes(value)
                    print(color(f"    Report Map: {len(self.report_map)} bytes", 'green'))
                    print(color(f"    Report Map (hex): {self.report_map.hex()}", 'cyan'))
                except Exception as e:
                    print(color(f"    Failed to read report map: {e}", 'red'))

            elif char.uuid == GATT_HID_REPORT_CHARACTERISTIC:
                # Discover descriptors to find report reference (pass characteristic as named argument)
                await self.peer.discover_descriptors(characteristic=char)

                report_id = 0
                report_type = HID_REPORT_TYPE_INPUT

                for desc in char.descriptors:
                    if desc.type == GATT_REPORT_REFERENCE_DESCRIPTOR:
                        try:
                            ref_value = await self.peer.read_value(desc)
                            if len(ref_value) >= 2:
                                report_id = ref_value[0]
                                report_type = ref_value[1]
                        except Exception as e:
                            print(color(f"    Failed to read report reference: {e}", 'yellow'))

                print(color(f"    Report ID: {report_id}, Type: {report_type}", 'cyan'))

                if report_type == HID_REPORT_TYPE_INPUT:
                    self.hid_reports[report_id] = char
                    # Don't subscribe yet - will do that after UHID device is created

        return True

    async def subscribe_to_reports(self):
        """Subscribe to HID input report notifications"""
        for report_id, char in self.hid_reports.items():
            try:
                await self.peer.subscribe(char, self._on_hid_report)
                print(color(f">>> Subscribed to input report {report_id}", 'green'))
            except Exception as e:
                print(color(f">>> Failed to subscribe to report {report_id}: {e}", 'yellow'))

    def _on_hid_report(self, value):
        """Handle incoming HID input reports"""
        report_data = bytes(value)
        print(color(f">>> HID Report: {report_data.hex()}", 'magenta'))

        if self.uhid_device:
            self.uhid_device.send_input(report_data)
        else:
            logging.error("Received HID report but uhid_device is None!")

    async def create_uhid_device(self, name: str = "BLE HID Device"):
        """Create a virtual HID device using UHID"""
        if not self.report_map:
            print(color(">>> No report map available!", 'red'))
            return False

        # Use dummy VID/PID for now
        vid = 0x0001
        pid = 0x0001

        self.uhid_device = UHIDDevice(name, vid, pid, self.report_map)
        return await self.uhid_device.create()

    async def run(self, target_address: str):
        """Main loop: connect, pair, discover HID, and receive reports"""
        try:
            await self.start()

            if target_address:
                await self.connect(target_address)
            else:
                # Scan and let user select
                devices = await self.scan(duration=10.0, filter_hid=True)
                if not devices:
                    print(color(">>> No HID devices found!", 'red'))
                    return

                print("\nSelect device:")
                for i, dev in enumerate(devices):
                    print(f"  {i+1}. {dev['name']} ({dev['address']})")

                choice = input("\nEnter number: ")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        target_address = devices[idx]['address']
                    else:
                        print("Invalid selection")
                        return
                except ValueError:
                    print("Invalid input")
                    return

                await self.connect(target_address)

            # Attempt pairing
            await self.pair()

            # Discover HID service
            if await self.discover_hid_service():
                # Create UHID device
                await self.create_uhid_device()

                print(color("\n>>> Receiving HID reports. Press Ctrl+C to exit.", 'green'))

                # Wait for disconnection or interrupt
                await self.transport.source.wait_for_termination()

        except KeyboardInterrupt:
            print(color("\n>>> Interrupted by user", 'yellow'))
        except Exception as e:
            print(color(f">>> Error: {e}", 'red'))
            logging.exception("Error in run()")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        if self.uhid_device:
            self.uhid_device.destroy()
        if self.connection:
            try:
                await self.connection.disconnect()
            except Exception:
                pass
        if hasattr(self, 'transport'):
            await self.transport.close()


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description='Kindle BLE HID Host using Google Bumble'
    )
    parser.add_argument(
        '-t', '--transport',
        default='file:/dev/stpbt',
        help='HCI transport specification (default: file:/dev/stpbt)'
    )
    parser.add_argument(
        '-c', '--config',
        help='Device configuration JSON file'
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

    args = parser.parse_args()

    # Configure logging (only if not already configured)
    log_level = logging.DEBUG if args.debug else logging.INFO
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s'
        )

    # Create and run the HID host
    host = BLEHIDHost(args.transport, args.config)
    await host.run(args.address)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C
