#!/usr/bin/env python3
"""
Kindle BLE HID Host using Google Bumble

This implements a BLE HID host that:
1. Connects to /dev/stpbt (MediaTek STP Bluetooth)
2. Scans for and connects to BLE HID devices
3. Handles SMP pairing (bypassing kernel SMP bug)
4. Parses HID over GATT (HOGP) reports
5. Executes shell scripts based on button presses

Author: Lucas Zampieri <lzampier@redhat.com>
Date: December 2025
"""

__version__ = "1.3.0"  # Cached GATT characteristics to skip 10s discovery

import asyncio
import argparse
import json
import logging
import os
import subprocess
import time

from bumble.device import Device, Peer
from bumble.hci import Address
from bumble.gatt import (
    GATT_GENERIC_ACCESS_SERVICE,
    GATT_DEVICE_NAME_CHARACTERISTIC,
    Characteristic,
    Descriptor,
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
GATT_HID_REPORT_CHARACTERISTIC = UUID.from_16_bits(0x2A4D)

# Report Reference Descriptor
GATT_REPORT_REFERENCE_DESCRIPTOR = UUID.from_16_bits(0x2908)
# Client Characteristic Configuration Descriptor
GATT_CCCD = UUID.from_16_bits(0x2902)

# HID Report Types
HID_REPORT_TYPE_INPUT = 1

# -----------------------------------------------------------------------------
# Configuration paths
# -----------------------------------------------------------------------------
# GATT cache directory
GATT_CACHE_DIR = '/mnt/us/bumble_ble_hid/cache'

# Pairing keys storage
PAIRING_KEYS_FILE = '/mnt/us/bumble_ble_hid/cache/pairing_keys.json'

# Button configuration file
BUTTON_CONFIG_FILE = '/mnt/us/bumble_ble_hid/button_config.json'

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


class ButtonScriptExecutor:
    """Execute shell scripts based on button presses"""

    def __init__(self, config_path: str = BUTTON_CONFIG_FILE):
        self.config_path = config_path
        self.button_scripts = {}
        self.debounce_ms = 500
        self.log_button_presses = True
        self.load_config()

    def load_config(self):
        """Load button-to-script mapping configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            self.button_scripts = config.get('buttons', {})
            self.debounce_ms = config.get('debounce_ms', 500)
            self.log_button_presses = config.get('log_button_presses', True)

            print(color(f">>> Loaded button configuration from {self.config_path}", 'green'))
            print(color(f">>> Configured {len(self.button_scripts)} button mappings", 'cyan'))
            for button_hex, script_path in self.button_scripts.items():
                print(color(f"    {button_hex} -> {script_path}", 'cyan'))

        except FileNotFoundError:
            print(color(f">>> Warning: Config file not found: {self.config_path}", 'yellow'))
            print(color(f">>> Using default empty configuration", 'yellow'))
        except json.JSONDecodeError as e:
            print(color(f">>> Error parsing config file: {e}", 'red'))
            print(color(f">>> Using default empty configuration", 'yellow'))

    def execute_button_script(self, button_code: int, button_name: str):
        """Execute the script mapped to a button press"""
        button_hex = f"0x{button_code:02x}"

        if self.log_button_presses:
            print(color(f">>> Button press: {button_name} (code: {button_hex})", 'green'))

        script_path = self.button_scripts.get(button_hex)

        if not script_path:
            print(color(f">>> No script configured for button {button_hex}", 'yellow'))
            return

        # Check if script exists
        if not os.path.exists(script_path):
            print(color(f">>> Script not found: {script_path}", 'red'))
            return

        # Execute script in background
        try:
            print(color(f">>> Executing: {script_path}", 'cyan'))
            subprocess.Popen(
                [script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent process
            )
            print(color(f">>> Script launched successfully", 'green'))
        except Exception as e:
            print(color(f">>> Failed to execute script: {e}", 'red'))


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
        self.button_executor = ButtonScriptExecutor()
        self.hid_reports = {}  # report_id -> characteristic
        self.report_map = None  # HID report map (cached for debugging)
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
            # Connection timeout is not an error - device might be off
            print(color(f">>> Connection timeout after {timeout}s (device may be off or out of range)", 'yellow'))
            return False

        self.peer = Peer(self.connection)

        print(color(f">>> Connected to {self.connection.peer_address}", 'green'))

        # Set up connection event handlers
        self.connection.on('disconnection', self._on_disconnection)
        self.connection.on('pairing', self._on_pairing)
        self.connection.on('pairing_failure', self._on_pairing_failure)

        return True

    def _on_disconnection(self, reason):
        print(color(f">>> Disconnected: reason={reason}", 'red'))

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
                    try:
                        await self.connection.encrypt()
                        print(color(">>> Bonding restored!", 'green'))
                        return True
                    except asyncio.CancelledError:
                        # Connection was terminated during encryption - likely bad cached keys
                        print(color(f">>> Cached keys rejected by device (disconnected), clearing cache", 'yellow'))
                        # Delete bad keys
                        try:
                            await self.device.keystore.delete(str(peer_address))
                        except:
                            pass
                        # Return False since connection is gone
                        return False
                    except Exception as enc_err:
                        print(color(f">>> Cached keys failed (reason: {enc_err}), clearing cache and re-pairing", 'yellow'))
                        # Delete bad keys
                        try:
                            await self.device.keystore.delete(str(peer_address))
                        except:
                            pass
                        # Continue to fresh pairing below
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

            if char.uuid == GATT_HID_INFORMATION_CHARACTERISTIC:
                # Read HID Information to detect device type (for logging only)
                try:
                    value = await self.peer.read_value(char)
                    if len(value) >= 4:
                        # HID Information format: [bcdHID(2), bCountryCode(1), Flags(1)]
                        # Flags byte bit 0-1: 00=reserved, 01=keyboard, 10=mouse, 11=reserved
                        flags = value[3]
                        device_type = flags & 0x03
                        device_type_name = {0: 'Unknown', 1: 'Keyboard', 2: 'Mouse', 3: 'Reserved'}.get(device_type, 'Unknown')
                        print(color(f"    HID Information: Device Type = {device_type_name} (0x{device_type:02x})", 'green'))
                except Exception as e:
                    print(color(f"    Failed to read HID Information: {e}", 'yellow'))

            elif char.uuid == GATT_HID_REPORT_MAP_CHARACTERISTIC:
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

        # 0xc6 pattern - also LEFT (release or alternate state)
        if button_state == 0xc6:
            return (0x01, "Button 1 (Left)")

        # 0x2c pattern - this is CENTER/SELECT button
        if button_state == 0x2c:
            return (0x10, "Button 5 (Center)")

        # 0xd5 pattern - this is ENTER/CONFIRM button
        if button_state == 0xd5:
            return (0x20, "Button 6 (Enter)")

        # For 0x68, we need to look at the exact movement pattern
        if button_state == 0x68:
            # Down: positive Y movement (typically 0x20 = +32)
            # Use threshold to ignore small positive jitter
            if y_signed > 15:
                return (0x08, "Button 4 (Down)")

            # Up: significant negative Y movement (need strong negative signal)
            # Threshold lowered to -15 to catch initial UP press (was -20)
            if y_signed < -15:
                # UP has x=0x00 (no X movement)
                # RIGHT has small positive x (like 0x01)
                if x_movement == 0x00:
                    return (0x02, "Button 2 (Up)")
                else:
                    return (0x04, "Button 3 (Right)")

            # Weak signals (y between -15 and +15) - ignore as noise/release events
            return (None, None)

        # Right button sometimes sends 0xFA
        if button_state == 0xFA:
            return (0x04, "Button 3 (Right)")

        # Fallback: send first set bit as button number
        for i in range(8):
            if button_state & (1 << i):
                return (1 << i, f"Button (bit {i})")

        return (None, None)

    def _on_hid_report(self, value):
        """Handle incoming HID input reports and execute button scripts"""
        report_data = bytes(value)

        # Button mapping with script execution is always enabled
        if len(report_data) < 2:
            return

        # Extract report ID, button state, and movement
        report_id = report_data[0]
        button_state = report_data[1]
        x_movement = report_data[2] if len(report_data) > 2 else 0
        y_movement = report_data[3] if len(report_data) > 3 else 0

        # Detect if any button is pressed (non-zero button state)
        if button_state != 0:
            # Debounce: ignore ANY button press within configured time (global across all report IDs)
            current_time = time.time()
            debounce_sec = self.button_executor.debounce_ms / 1000.0

            if current_time - self.last_press_time < debounce_sec:
                return

            # Map the button combination to a clean single button using movement direction
            mapped_button, button_name = self._map_button_combination(button_state, x_movement, y_movement)

            if mapped_button is None:
                print(color(f"    Unknown button combination: 0x{button_state:02x}", 'yellow'))
                return

            print(color(f">>> Detected: {button_name} (raw: 0x{button_state:02x}, x:{x_movement:02x}, y:{y_movement:02x})", 'cyan'))

            # Execute the script for this button
            self.button_executor.execute_button_script(mapped_button, button_name)

            # Update global debounce timestamp
            self.last_press_time = current_time


    async def run(self, target_address: str):
        """Main loop: connect, pair, discover HID, and receive reports"""
        disconnection_event = asyncio.Event()

        def on_disconnection_wrapper(reason):
            """Wrapper to signal disconnection event"""
            self._on_disconnection(reason)
            disconnection_event.set()

        try:
            await self.start()

            if target_address:
                connected = await self.connect(target_address)
                if not connected:
                    # Connection failed (timeout) - return to let daemon retry
                    return
            else:
                # Scan continuously until devices are found
                devices = []
                while not devices:
                    devices = await self.scan(duration=10.0, filter_hid=True)
                    if not devices:
                        print(color(">>> No HID devices found. Scanning again in 3 seconds...", 'yellow'))
                        print(color(">>> (Make sure your device is in pairing mode. Press Ctrl+C to exit)", 'cyan'))
                        await asyncio.sleep(3)

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

                connected = await self.connect(target_address)
                if not connected:
                    # Connection failed (timeout) - return to let daemon retry
                    return

            # Replace the disconnection handler with our wrapper
            self.connection.on('disconnection', on_disconnection_wrapper)

            # Attempt pairing
            paired = await self.pair()
            if not paired:
                print(color(">>> Pairing failed, exiting", 'red'))
                return

            # Discover HID service
            if await self.discover_hid_service():
                # Subscribe to HID reports
                await self.subscribe_to_reports()

                print(color("\n>>> Receiving HID reports and executing button scripts. Press Ctrl+C to exit.", 'green'))

                # Wait for disconnection event
                try:
                    await disconnection_event.wait()
                    print(color("\n>>> Connection terminated", 'yellow'))
                except asyncio.CancelledError:
                    print(color("\n>>> Connection cancelled", 'yellow'))

        except KeyboardInterrupt:
            print(color("\n>>> Interrupted by user", 'yellow'))
        except asyncio.CancelledError:
            print(color("\n>>> Connection cancelled", 'yellow'))
        except Exception as e:
            print(color(f">>> Error: {e}", 'red'))
            logging.exception("Error in run()")
        finally:
            await self.cleanup()
            print(color(">>> Run method completed, returning to caller", 'yellow'))

    async def cleanup(self):
        """Clean up resources"""
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
    parser.add_argument(
        '--scan-only',
        action='store_true',
        help='Scan for devices and exit (for setup script)'
    )
    parser.add_argument(
        '--scan-duration',
        type=int,
        default=30,
        help='Duration to scan for devices in seconds (default: 30)'
    )

    args = parser.parse_args()

    # Configure logging (only if not already configured)
    log_level = logging.DEBUG if args.debug else logging.INFO
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s'
        )

    # Handle scan-only mode
    if args.scan_only:
        print(color(">>> Scanning for BLE devices...", 'cyan'))
        host = BLEHIDHost(args.transport, args.config)
        try:
            await host.start()
            devices = await host.scan(duration=args.scan_duration, filter_hid=False)

            if devices:
                print(color(f"\n>>> Found {len(devices)} BLE device(s):", 'green'))
                for dev in devices:
                    print(f"  {dev['name']:30s} {dev['address']}")
            else:
                print(color("\n>>> No BLE devices found", 'yellow'))
                print(color(">>> Make sure your device is in pairing mode", 'yellow'))

            await host.cleanup()
        except Exception as e:
            print(color(f">>> Error during scan: {e}", 'red'))
            logging.exception("Scan error")
        return

    # Load device address from devices.conf if not specified
    target_address = args.address
    if not target_address:
        devices_conf = '/mnt/us/bumble_ble_hid/devices.conf'
        if os.path.exists(devices_conf):
            with open(devices_conf, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        target_address = line
                        print(color(f">>> Using device from devices.conf: {target_address}", 'cyan'))
                        break

    # Create and run the HID host
    host = BLEHIDHost(args.transport, args.config)
    await host.run(target_address)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C
