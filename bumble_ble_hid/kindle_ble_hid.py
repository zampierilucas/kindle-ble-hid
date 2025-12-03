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

__version__ = "1.3.0"  # Cached GATT characteristics to skip 10s discovery

import asyncio
import argparse
import json
import logging
import os
import struct
import sys
import time

from bumble.device import Device, Peer
from bumble.hci import Address
from bumble.gatt import (
    GATT_GENERIC_ACCESS_SERVICE,
    GATT_DEVICE_NAME_CHARACTERISTIC,
)
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.keys import JsonKeyStore
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

# GATT cache directory
GATT_CACHE_DIR = '/mnt/us/bumble_ble_hid/cache'

# Pairing keys storage
PAIRING_KEYS_FILE = '/mnt/us/bumble_ble_hid/cache/pairing_keys.json'

# Timestamp tracker for performance debugging
_last_timestamp = None
_original_print = print

def _timestamped_print(*args, **kwargs):
    """Print with automatic timestamp and delta"""
    global _last_timestamp

    # Check if first arg is a string (plain or from color()) containing ">>>"
    if args and len(args) > 0:
        first_arg = str(args[0])
        if ">>>" in first_arg:
            current = time.time()

            if _last_timestamp is None:
                delta_str = ""
            else:
                delta = current - _last_timestamp
                delta_str = f" (+{delta:.3f}s)"

            _last_timestamp = current
            timestamp_str = time.strftime("%H:%M:%S", time.localtime(current))

            # Modify the first argument to prepend timestamp
            # Handle both plain strings and colored strings
            if isinstance(args[0], str):
                args = (f"[{timestamp_str}]{delta_str} {args[0]}",) + args[1:]
            else:
                # For colored strings, we need to preserve the color formatting
                # Just print timestamp separately
                _original_print(f"[{timestamp_str}]{delta_str}", end=" ")

    _original_print(*args, **kwargs)

# Override print for this module
print = _timestamped_print

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
        self.event_loop_task = None

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

            # Start event loop to handle kernel responses
            self.event_loop_task = asyncio.create_task(self._event_loop())

            return True
        except OSError as e:
            logging.error(f"Failed to create UHID device: {e}")
            return False

    async def _event_loop(self):
        """Read and handle kernel events from UHID"""
        print(color(">>> UHID event loop started", 'green'))

        while self.running:
            try:
                # Use asyncio to avoid blocking (10Hz polling is sufficient for HID)
                await asyncio.sleep(0.1)

                # Try to read event from kernel
                try:
                    data = os.read(self.fd, 4096)
                except BlockingIOError:
                    # No data available (non-blocking read)
                    continue
                except OSError as e:
                    logging.error(f"Error reading UHID event: {e}")
                    break

                if len(data) < 4:
                    continue

                # Parse event type
                event_type = struct.unpack('<I', data[:4])[0]

                if event_type == UHID_START:
                    print(color(">>> UHID: Received START from kernel", 'green'))
                elif event_type == UHID_STOP:
                    print(color(">>> UHID: Received STOP from kernel", 'yellow'))
                elif event_type == UHID_OPEN:
                    print(color(">>> UHID: Received OPEN from kernel (device ready!)", 'green'))
                elif event_type == UHID_CLOSE:
                    print(color(">>> UHID: Received CLOSE from kernel", 'yellow'))
                elif event_type == UHID_OUTPUT:
                    # Output report from kernel (e.g., LED state for keyboard)
                    if len(data) >= 6:
                        size = struct.unpack('<H', data[4:6])[0]
                        output_data = data[6:6+size]
                        print(color(f">>> UHID: Received OUTPUT from kernel: {output_data.hex()}", 'cyan'))
                else:
                    print(color(f">>> UHID: Unknown event type: {event_type}", 'yellow'))

            except Exception as e:
                logging.error(f"Error in UHID event loop: {e}")

        print(color(">>> UHID event loop stopped", 'yellow'))

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
                self.running = False

                # Cancel event loop task
                if self.event_loop_task and not self.event_loop_task.done():
                    self.event_loop_task.cancel()

                event = struct.pack('<I', UHID_DESTROY)
                try:
                    os.write(self.fd, event)
                except OSError:
                    pass

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
        self.last_button_state = {}  # report_id -> button_state (to detect changes)
        self.last_press_time = 0  # Global timestamp for debouncing (across all report IDs)
        self.current_device_address = None  # Track connected device for cache
        self.device_name = None  # BLE device name from Generic Access Service

    async def start(self):
        """Initialize the Bumble device"""
        print(color(f">>> Kindle BLE HID Host v{__version__}", 'cyan'))
        print(color(">>> Opening transport...", 'blue'))
        self.transport = await open_transport(self.transport_spec)

        # Set up persistent key store for bonding
        key_store = JsonKeyStore(namespace=None, filename=PAIRING_KEYS_FILE)

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

        # Attach key store to device
        self.device.keystore = key_store

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

        # Track device address for cache
        self.current_device_address = address

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
        """Initiate pairing with the connected device (or use cached keys if available)"""
        if not self.connection:
            print(color(">>> Not connected!", 'red'))
            return False

        # Check if we have bonding keys for this device
        peer_address = self.connection.peer_address
        if self.device.keystore:
            try:
                keys = await self.device.keystore.get(str(peer_address))
                if keys:
                    print(color(f">>> Using cached bonding keys for {peer_address}", 'cyan'))
                    # Request encryption (will use cached keys)
                    await self.connection.encrypt()
                    print(color(">>> Bonding restored!", 'green'))
                    return True
            except Exception as e:
                print(color(f">>> No cached keys found, will pair: {e}", 'yellow'))

        # No cached keys, perform full pairing
        print(color(">>> Initiating pairing...", 'blue'))
        try:
            await self.connection.pair()
            print(color(">>> Pairing complete!", 'green'))
            return True
        except Exception as e:
            print(color(f">>> Pairing error: {e}", 'red'))
            return False

    def _get_cache_path(self, address: str):
        """Get cache file path for device address"""
        safe_addr = address.replace(':', '_').replace('/', '_')
        return os.path.join(GATT_CACHE_DIR, f"{safe_addr}.json")

    def _load_cache(self, address: str):
        """Load cached GATT attributes for device"""
        cache_path = self._get_cache_path(address)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r') as f:
                cache = json.load(f)
                # Validate cache structure
                if 'report_map' not in cache:
                    logging.warning(f"Invalid cache structure for {address}")
                    return None
                print(color(f">>> Loaded GATT cache for {address}", 'green'))
                return cache
        except Exception as e:
            logging.warning(f"Failed to load cache for {address}: {e}")
            return None

    def _save_cache(self, address: str, cache_data: dict):
        """Save GATT attributes to cache"""
        try:
            os.makedirs(GATT_CACHE_DIR, exist_ok=True)
            cache_path = self._get_cache_path(address)
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            print(color(f">>> Saved GATT cache for {address}", 'green'))
        except Exception as e:
            logging.warning(f"Failed to save cache for {address}: {e}")

    async def discover_hid_service(self):
        """Discover and subscribe to HID service characteristics"""
        if not self.peer:
            print(color(">>> Not connected!", 'red'))
            return False

        # Try to load from cache first
        cache = None
        if self.current_device_address:
            cache = self._load_cache(self.current_device_address)
            if cache:
                try:
                    # Restore report map from cache
                    self.report_map = bytes.fromhex(cache['report_map'])
                    print(color(f">>> Using cached report map ({len(self.report_map)} bytes)", 'green'))

                    # Restore device name from cache if available
                    if 'device_name' in cache and cache['device_name']:
                        self.device_name = cache['device_name']
                        print(color(f">>> Using cached device name: {self.device_name}", 'green'))

                    # Note: We still need to discover services to get characteristic handles
                    # but we skip reading the report map
                    print(color(">>> Discovering GATT services (using cached data)...", 'blue'))
                except Exception as e:
                    logging.warning(f"Cache corrupt, re-discovering: {e}")
                    cache = None

        if not cache:
            print(color(">>> Discovering GATT services...", 'blue'))

        # Discover all services
        await self.peer.discover_services()

        # Read device name from Generic Access Service (skip if cached)
        if not self.device_name:
            try:
                generic_access_services = [s for s in self.peer.services if s.uuid == GATT_GENERIC_ACCESS_SERVICE]
                if generic_access_services:
                    await self.peer.discover_characteristics(service=generic_access_services[0])
                    device_name_chars = [c for c in generic_access_services[0].characteristics
                                        if c.uuid == GATT_DEVICE_NAME_CHARACTERISTIC]
                    if device_name_chars:
                        name_value = await self.peer.read_value(device_name_chars[0])
                        self.device_name = bytes(name_value).decode('utf-8', errors='replace')
                        print(color(f">>> Device Name: {self.device_name}", 'cyan'))
                        # Note: Cache will be saved after report_map is read
            except Exception as e:
                logging.warning(f"Could not read device name: {e}")
        else:
            print(color(f">>> Device Name: {self.device_name} (cached)", 'cyan'))

        # Find HID service
        hid_services = [s for s in self.peer.services if s.uuid == GATT_HID_SERVICE]

        if not hid_services:
            print(color(">>> HID service not found!", 'red'))
            return False

        hid_service = hid_services[0]
        print(color(f">>> Found HID service: {hid_service.uuid}", 'green'))

        # Check if we have cached characteristics
        characteristics_cached = False
        if cache and 'characteristics' in cache:
            print(color(">>> Loading characteristics from cache...", 'cyan'))
            try:
                # Reconstruct characteristics from cache
                from bumble.gatt import Characteristic
                cached_chars = []
                for char_data in cache['characteristics']:
                    # Parse UUID - handle both short form ("2A4B") and full form
                    uuid_str = char_data['uuid']

                    # Convert short form to full UUID if needed
                    if len(uuid_str) == 4:
                        uuid_str = f"0000{uuid_str}-0000-1000-8000-00805F9B34FB"
                    elif not uuid_str.startswith('0000'):
                        # Invalid format, skip this cache
                        raise ValueError(f"Invalid UUID format in cache: {uuid_str}")

                    # Create a proper Bumble Characteristic with CCCD descriptor pre-populated
                    # This avoids slow descriptor discovery while maintaining notification routing
                    from bumble.gatt import Characteristic, Descriptor

                    # Create the characteristic
                    char = Characteristic(
                        uuid=UUID(uuid_str),
                        properties=char_data.get('properties', 0),
                        permissions=0,  # Will be set by server if needed
                        value=b''  # Empty value for notifications
                    )
                    char.handle = char_data['handle']
                    char.end_group_handle = char_data['handle'] + 2  # Char + CCCD + padding
                    char.service = hid_service  # Link to parent service

                    # Create CCCD descriptor at handle+1 (standard BLE convention)
                    # This is what enables notifications without discovery
                    cccd = Descriptor(
                        attribute_type=GATT_CCCD,
                        permissions=0,
                        value=b'\x00\x00'  # Default: notifications disabled
                    )
                    cccd.handle = char_data['handle'] + 1
                    cccd.characteristic = char  # Link descriptor to characteristic

                    # Attach descriptor to characteristic and mark as discovered
                    char.descriptors = [cccd]
                    char.descriptors_discovered = True  # Skip descriptor discovery
                    cached_chars.append(char)

                # Replace service characteristics with cached ones
                hid_service.characteristics = cached_chars
                characteristics_cached = True
                print(color(f">>> Loaded {len(cached_chars)} characteristics from cache", 'green'))
            except Exception as e:
                logging.warning(f"Failed to load cached characteristics: {e}")
                characteristics_cached = False

        # Discover characteristics if not cached (pass service as named argument)
        if not characteristics_cached:
            print(color(">>> Discovering characteristics...", 'cyan'))
            await self.peer.discover_characteristics(service=hid_service)
            print(color(f">>> Discovered {len(hid_service.characteristics)} characteristics", 'green'))

        # Track report references and characteristics for caching
        report_refs = {}
        characteristics_to_cache = []

        for char in hid_service.characteristics:
            print(color(f"    Characteristic: {char.uuid}", 'cyan'))

            # Collect characteristic for caching (if not already cached)
            if not characteristics_cached:
                # Store UUID as full hex string (with dashes) for reliable reconstruction
                uuid_hex = char.uuid.to_hex_str()
                # Convert short form (e.g., "2A4B") to full UUID format
                if len(uuid_hex) == 4:
                    uuid_full = f"0000{uuid_hex}-0000-1000-8000-00805F9B34FB"
                else:
                    uuid_full = uuid_hex  # Already in full format

                characteristics_to_cache.append({
                    'uuid': uuid_full,
                    'handle': char.handle,
                    'properties': getattr(char, 'properties', 0)
                })

            if char.uuid == GATT_HID_REPORT_MAP_CHARACTERISTIC:
                # Read report map (HID descriptor) only if not cached
                if not self.report_map:
                    try:
                        value = await self.peer.read_value(char)
                        self.report_map = bytes(value)
                        print(color(f"    Report Map: {len(self.report_map)} bytes", 'green'))
                        print(color(f"    Report Map (hex): {self.report_map.hex()}", 'cyan'))

                        # Save to cache (will be augmented with device_name later)
                        if self.current_device_address:
                            cache_data = {
                                'report_map': self.report_map.hex(),
                                'device_name': self.device_name  # May be None initially
                            }
                            self._save_cache(self.current_device_address, cache_data)
                    except Exception as e:
                        print(color(f"    Failed to read report map: {e}", 'red'))
                else:
                    print(color(f"    Using cached Report Map: {len(self.report_map)} bytes", 'cyan'))

            elif char.uuid == GATT_HID_REPORT_CHARACTERISTIC:
                # Check cache for report reference first
                report_id = 0
                report_type = HID_REPORT_TYPE_INPUT
                cached_report_ref = None

                if cache and 'report_refs' in cache:
                    # Try to find cached report reference for this handle
                    handle_key = str(char.handle)
                    if handle_key in cache['report_refs']:
                        cached_report_ref = cache['report_refs'][handle_key]
                        report_id = cached_report_ref['id']
                        report_type = cached_report_ref['type']
                        print(color(f"    Report ID: {report_id}, Type: {report_type} (cached)", 'cyan'))

                if not cached_report_ref:
                    # Discover descriptors to find report reference (pass characteristic as named argument)
                    await self.peer.discover_descriptors(characteristic=char)

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

                # Store report reference for caching (even if not input report)
                if not cached_report_ref:
                    report_refs[str(char.handle)] = {
                        'id': report_id,
                        'type': report_type
                    }

        # Update cache with report references and characteristics if we discovered any new ones
        if (report_refs or characteristics_to_cache) and self.current_device_address:
            try:
                updates = []
                if report_refs:
                    updates.append(f"{len(report_refs)} report references")
                if characteristics_to_cache:
                    updates.append(f"{len(characteristics_to_cache)} characteristics")
                print(color(f">>> Updating cache with {', '.join(updates)}...", 'blue'))

                # Load existing cache or create new one
                existing_cache = self._load_cache(self.current_device_address)
                if not existing_cache:
                    existing_cache = {}

                # Update with new report refs
                if report_refs:
                    if 'report_refs' not in existing_cache:
                        existing_cache['report_refs'] = {}
                    existing_cache['report_refs'].update(report_refs)

                # Update with new characteristics
                if characteristics_to_cache:
                    existing_cache['characteristics'] = characteristics_to_cache

                # Ensure report_map and device_name are present
                if self.report_map:
                    existing_cache['report_map'] = self.report_map.hex()
                if self.device_name:
                    existing_cache['device_name'] = self.device_name

                self._save_cache(self.current_device_address, existing_cache)
                print(color(f">>> Cache updated successfully", 'green'))
            except Exception as e:
                logging.warning(f"Failed to update cache: {e}")
        else:
            print(color(">>> All data loaded from cache", 'green'))

        return True

    async def subscribe_to_reports(self):
        """Subscribe to HID input report notifications serially"""
        # Subscribe to all reports serially to test timing behavior
        for report_id, char in self.hid_reports.items():
            try:
                await self.peer.subscribe(char, self._on_hid_report)
                print(color(f">>> Subscribed to input report {report_id}", 'green'))
            except Exception as e:
                print(color(f">>> Failed to subscribe to report {report_id}: {e}", 'yellow'))

    def _map_button_combination(self, button_state, x_movement=0, y_movement=0):
        """
        Map device's button combinations to clean individual buttons.

        LEGACY: This is BLE-M3 specific logic kept for backwards compatibility.
        Only active when KINDLE_BLE_HID_PATCH_DESCRIPTOR is enabled.

        The clicker is weird - it sends mouse movement data with button presses,
        and the movement patterns help distinguish which button was pressed.

        Returns: (mapped_button_code, button_name) or (None, None) if unknown
        """
        # Convert signed bytes to signed integers
        x_signed = x_movement if x_movement < 128 else x_movement - 256
        y_signed = y_movement if y_movement < 128 else y_movement - 256

        # 0x96 pattern - this is LEFT
        if button_state == 0x96:
            return (0x01, "Button 1 (Left)")

        # 0x2c pattern - this is CENTER/SELECT button
        if button_state == 0x2c:
            return (0x10, "Button 5 (Center)")

        # 0xd5 pattern - this is ENTER/CONFIRM button
        if button_state == 0xd5:
            return (0x20, "Button 6 (Enter)")

        # For 0x68, we need to look at the exact movement pattern
        if button_state == 0x68:
            # Down: positive Y movement (0x20 = 32)
            if y_signed > 0:
                return (0x08, "Button 4 (Down)")

            # For negative Y (up movement with button 0x68):
            # - UP has x=0x00 (no X movement)
            # - RIGHT has small positive x (like 0x01)
            if x_movement == 0x00:
                return (0x02, "Button 2 (Up)")
            else:
                return (0x04, "Button 3 (Right)")

        # Right button sometimes sends 0xFA
        if button_state == 0xFA:
            return (0x04, "Button 3 (Right)")

        # Fallback: send first set bit as button number
        for i in range(8):
            if button_state & (1 << i):
                return (1 << i, f"Button (bit {i})")

        return (None, None)

    def _on_hid_report(self, value):
        """Handle incoming HID input reports"""
        report_data = bytes(value)
        print(color(f">>> HID Report: {report_data.hex()}", 'magenta'))

        if not self.uhid_device:
            logging.error("Received HID report but uhid_device is None!")
            return

        # Check if BLE-M3 specific processing is enabled
        enable_ble_m3_logic = os.environ.get('KINDLE_BLE_HID_PATCH_DESCRIPTOR', '').lower() in ('1', 'true', 'yes')

        if enable_ble_m3_logic:
            # LEGACY BLE-M3 specific processing with button mapping and debouncing
            if len(report_data) < 2:
                return

            # Extract report ID, button state, and movement
            report_id = report_data[0]
            button_state = report_data[1]
            x_movement = report_data[2] if len(report_data) > 2 else 0
            y_movement = report_data[3] if len(report_data) > 3 else 0

            # Detect if any button is pressed (non-zero button state)
            if button_state != 0:
                # Debounce: ignore ANY button press within 500ms (global across all report IDs)
                current_time = time.time()

                if current_time - self.last_press_time < 0.5:
                    print(color(f"    Debounced (too soon)", 'blue'))
                    return

                # Map the button combination to a clean single button using movement direction
                mapped_button, button_name = self._map_button_combination(button_state, x_movement, y_movement)

                if mapped_button is None:
                    print(color(f"    Unknown button combination: 0x{button_state:02x}", 'yellow'))
                    return

                print(color(f"    Detected: {button_name} (raw: 0x{button_state:02x}, x:{x_movement:02x}, y:{y_movement:02x})", 'cyan'))

                # Create clean button report with mapped button
                clean_data = bytearray(report_data)
                clean_data[1] = mapped_button  # Replace with clean single button

                # Send the press event
                translated_data = self._translate_report_id(bytes(clean_data))
                self.uhid_device.send_input(translated_data)
                print(color(f"    Sent clean button: 0x{mapped_button:02x}", 'green'))

                # Immediately synthesize a release event (all buttons off)
                release_data = bytearray(report_data)
                release_data[1] = 0x00  # Clear all buttons
                translated_release = self._translate_report_id(bytes(release_data))
                self.uhid_device.send_input(translated_release)
                print(color(f"    Auto-release sent", 'yellow'))

                # Update global debounce timestamp
                self.last_press_time = current_time
        else:
            # Pure pass-through mode: send reports as-is to UHID
            print(color(f"    Pure pass-through mode: forwarding report unchanged", 'cyan'))
            self.uhid_device.send_input(report_data)

    def _translate_report_id(self, report_data):
        """
        Translate invalid report IDs (0, 7) to valid ones (5, 7).
        HID doesn't allow report ID 0.
        """
        if len(report_data) < 1:
            return report_data

        report_id = report_data[0]

        # Translate ID 0 -> 5 (0 is reserved in HID spec)
        if report_id == 0x00:
            print(color(f"    Translating report ID 0x00 -> 0x05", 'yellow'))
            return bytes([0x05]) + report_data[1:]

        return report_data

    def _create_permissive_descriptor(self):
        """
        Create a permissive HID descriptor that accepts any report format.

        This descriptor:
        - Uses Mouse usage (gets recognized as input device)
        - Declares Report IDs 0-15 with 63-byte payloads
        - Pure pass-through: forwards any data unchanged
        - Works with any BLE HID device regardless of descriptor mismatches
        """
        descriptor = bytes([
            # Usage Page (Generic Desktop)
            0x05, 0x01,

            # Usage (Mouse)
            0x09, 0x02,

            # Collection (Application)
            0xA1, 0x01,
        ])

        # Create 16 report IDs (IDs 0-15) with identical 63-byte payloads
        # Each report declares mouse buttons + vendor data
        for report_id in range(0, 16):
            descriptor += bytes([
                # Report ID (1-15, skip 0 as it's reserved)
                0x85, report_id if report_id > 0 else 1,

                # Usage Page (Button)
                0x05, 0x09,

                # Usage Minimum (Button 1)
                0x19, 0x01,

                # Usage Maximum (Button 8)
                0x29, 0x08,

                # Logical Minimum (0)
                0x15, 0x00,

                # Logical Maximum (1)
                0x25, 0x01,

                # Report Count (8 buttons)
                0x95, 0x08,

                # Report Size (1 bit per button)
                0x75, 0x01,

                # Input (Data, Variable, Absolute)
                0x81, 0x02,

                # Usage Page (Generic Desktop)
                0x05, 0x01,

                # Usage (X, Y, Wheel)
                0x09, 0x30,  # X
                0x09, 0x31,  # Y
                0x09, 0x38,  # Wheel

                # Logical Minimum (-127)
                0x15, 0x81,

                # Logical Maximum (127)
                0x25, 0x7F,

                # Report Count (3 axes)
                0x95, 0x03,

                # Report Size (8 bits)
                0x75, 0x08,

                # Input (Data, Variable, Relative)
                0x81, 0x06,

                # Padding: 59 bytes of vendor-specific data (63 total - 1 button byte - 3 axis bytes)
                # Usage Page (Vendor Defined)
                0x06, 0x00, 0xFF,

                # Usage (Vendor Usage 1)
                0x09, 0x01,

                # Logical Minimum (0)
                0x15, 0x00,

                # Logical Maximum (255)
                0x26, 0xFF, 0x00,

                # Report Count (59 bytes)
                0x95, 0x3B,

                # Report Size (8 bits)
                0x75, 0x08,

                # Input (Data, Variable, Absolute)
                0x81, 0x02,
            ])

        descriptor += bytes([
            # End Collection
            0xC0,
        ])

        print(color(f"    Using permissive Mouse descriptor (16 Report IDs, 63-byte payload each)", 'cyan'))
        return descriptor

    async def create_uhid_device(self, name: str = None):
        """Create a virtual HID device using UHID

        Args:
            name: Optional name override. If not provided, uses self.device_name
                  (from Generic Access Service), falling back to "BLE HID Device"
        """
        if not self.report_map:
            print(color(">>> No report map available!", 'red'))
            return False

        # Use actual device name if available, otherwise fall back to provided name or default
        if name is None:
            if self.device_name:
                name = self.device_name
            else:
                name = "BLE HID Device"

        # Check mode: permissive (default) or original descriptor
        use_original = os.environ.get('KINDLE_BLE_HID_USE_ORIGINAL_DESCRIPTOR', '').lower() in ('1', 'true', 'yes')

        if use_original:
            print(color(">>> Using original report descriptor from device", 'green'))
            descriptor = self.report_map
        else:
            print(color(">>> Using permissive vendor-specific descriptor (default)", 'cyan'))
            descriptor = self._create_permissive_descriptor()

        # Use dummy VID/PID for now
        vid = 0x0001
        pid = 0x0001

        print(color(f">>> Creating UHID device: {name}", 'cyan'))
        self.uhid_device = UHIDDevice(name, vid, pid, descriptor)
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
