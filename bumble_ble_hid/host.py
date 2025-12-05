#!/usr/bin/env python3
"""
BLE HID Host

Core BLE stack implementation using Google Bumble.
Handles connection, pairing, GATT discovery, and HID report subscription.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

__version__ = "2.0.0"  # Refactored modular architecture

import asyncio
import logging
from typing import Optional

from bumble.device import Device, Peer
from bumble.hci import Address, HCI_Reset_Command
from bumble.gatt import (
    GATT_GENERIC_ACCESS_SERVICE,
    GATT_DEVICE_NAME_CHARACTERISTIC,
    Characteristic,
    Descriptor,
)
from bumble.transport import open_transport
from bumble.core import UUID, AdvertisingData

from config import config
from logging_utils import log, color
from gatt_cache import GATTCache
from button_handler import ButtonHandler
from pairing import create_pairing_config, create_keystore

__all__ = ['BLEHIDHost', '__version__']

# BLE HID Service UUIDs (Bluetooth SIG)
GATT_HID_SERVICE = UUID.from_16_bits(0x1812)
GATT_HID_INFORMATION_CHARACTERISTIC = UUID.from_16_bits(0x2A4A)
GATT_HID_REPORT_MAP_CHARACTERISTIC = UUID.from_16_bits(0x2A4B)
GATT_HID_REPORT_CHARACTERISTIC = UUID.from_16_bits(0x2A4D)
GATT_REPORT_REFERENCE_DESCRIPTOR = UUID.from_16_bits(0x2908)
GATT_CCCD = UUID.from_16_bits(0x2902)

# HID Report Types
HID_REPORT_TYPE_INPUT = 1


class BLEHIDHost:
    """BLE HID Host that connects to HID devices and handles input.

    This class manages the BLE connection lifecycle:
    1. Transport initialization and HCI reset
    2. Device scanning (optional)
    3. Connection establishment
    4. SMP pairing with key persistence
    5. GATT service discovery (with caching)
    6. HID report subscription
    7. Button event processing
    """

    def __init__(self, transport_spec: str = None):
        """Initialize BLE HID Host.

        Args:
            transport_spec: HCI transport (default: from config)
        """
        self.transport_spec = transport_spec or config.transport
        self.device = None
        self.connection = None
        self.peer = None
        self.transport = None

        # Components
        self.gatt_cache = GATTCache(config.cache_dir)
        self.button_handler = ButtonHandler()
        self.keystore = create_keystore(config.pairing_keys_file)

        # State
        self.hid_reports = {}  # report_id -> characteristic
        self.report_map = None
        self.current_device_address = None
        self.device_name = None

    async def start(self):
        """Initialize the Bumble device and BLE stack.

        Raises:
            asyncio.TimeoutError: If transport or HCI reset times out
        """
        log.info(f"Kindle BLE HID Host v{__version__}")
        log.info("Opening transport...")

        try:
            self.transport = await asyncio.wait_for(
                open_transport(self.transport_spec),
                timeout=config.transport_timeout
            )
        except asyncio.TimeoutError:
            log.error(f"Transport open timed out after {config.transport_timeout}s")
            raise

        # Create Bumble device
        self.device = Device.with_hci(
            config.device_name,
            config.device_address,
            self.transport.source,
            self.transport.sink
        )

        # Attach key store and pairing config
        self.device.keystore = self.keystore
        self.device.pairing_config_factory = lambda conn: create_pairing_config()

        # HCI Reset - critical for sleep recovery
        log.info("Sending HCI Reset...")
        try:
            await asyncio.wait_for(
                self.device.host.send_command(HCI_Reset_Command()),
                timeout=config.hci_reset_timeout
            )
            log.success("HCI Reset successful")
        except asyncio.TimeoutError:
            log.error(f"HCI Reset timed out after {config.hci_reset_timeout}s - "
                     "BT hardware may be asleep")
            raise

        await self.device.power_on()
        log.success(f"Device powered on: {self.device.public_address}")

    async def scan(self, duration: float = 10.0, filter_hid: bool = True):
        """Scan for BLE devices.

        Args:
            duration: Scan duration in seconds
            filter_hid: If True, only return devices advertising HID service

        Returns:
            List of device dicts with address, name, rssi, is_hid
        """
        log.info(f"Scanning for {duration} seconds...")

        devices_found = []
        seen_addresses = set()

        def on_advertisement(advertisement):
            addr_str = str(advertisement.address)

            if addr_str in seen_addresses:
                return
            seen_addresses.add(addr_str)

            # Extract device name
            name = 'Unknown'
            if hasattr(advertisement, 'data') and advertisement.data:
                name = advertisement.data.get(AdvertisingData.COMPLETE_LOCAL_NAME)
                if not name:
                    name = advertisement.data.get(AdvertisingData.SHORTENED_LOCAL_NAME)
                if not name:
                    name = 'Unknown'
                if isinstance(name, bytes):
                    name = name.decode('utf-8', errors='replace')

            # Check for HID service
            is_hid = False
            if hasattr(advertisement, 'data') and advertisement.data:
                services = advertisement.data.get(
                    AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS
                )
                if not services:
                    services = advertisement.data.get(
                        AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS
                    )
                if services:
                    for service_uuid in services:
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
                log.detail(f"Found: {entry['name']} ({entry['address']}) "
                          f"RSSI: {entry['rssi']}{hid_marker}")

        self.device.on('advertisement', on_advertisement)
        await self.device.start_scanning(filter_duplicates=True)
        await asyncio.sleep(duration)
        await self.device.stop_scanning()

        log.success(f"Scan complete. Found {len(devices_found)} devices.")
        return devices_found

    async def connect(self, address: str) -> bool:
        """Connect to a BLE device.

        Args:
            address: BLE device address

        Returns:
            True if connected, False on timeout
        """
        log.info(f"Connecting to {address}...")
        self.current_device_address = address

        target = Address(address)
        try:
            self.connection = await asyncio.wait_for(
                self.device.connect(target),
                timeout=config.connect_timeout
            )
        except asyncio.TimeoutError:
            log.warning(f"Connection timeout after {config.connect_timeout}s "
                       "(device may be off or out of range)")
            return False

        self.peer = Peer(self.connection)
        log.success(f"Connected to {self.connection.peer_address}")

        # Set up event handlers
        self.connection.on('pairing', self._on_pairing)
        self.connection.on('pairing_failure', self._on_pairing_failure)

        return True

    async def pair(self) -> bool:
        """Pair with connected device (or restore bonding).

        Returns:
            True if paired/bonded, False on failure
        """
        if not self.connection:
            log.error("Not connected!")
            return False

        peer_address = self.connection.peer_address

        # Try cached keys first
        if self.device.keystore:
            try:
                keys = await self.device.keystore.get(str(peer_address))
                if keys:
                    log.info(f"Using cached bonding keys for {peer_address}")
                    try:
                        await self.connection.encrypt()
                        log.success("Bonding restored!")
                        return True
                    except asyncio.CancelledError:
                        log.warning("Cached keys rejected (disconnected), clearing cache")
                        try:
                            await self.device.keystore.delete(str(peer_address))
                        except:
                            pass
                        return False
                    except Exception as enc_err:
                        log.warning(f"Cached keys failed ({enc_err}), re-pairing")
                        try:
                            await self.device.keystore.delete(str(peer_address))
                        except:
                            pass
            except Exception as e:
                log.warning(f"No cached keys found, will pair: {e}")

        # Full pairing
        log.info("Initiating pairing...")
        try:
            await self.connection.pair()
            log.success("Pairing complete!")
            return True
        except Exception as e:
            log.error(f"Pairing error: {e}")
            return False

    async def discover_hid_service(self) -> bool:
        """Discover HID service and characteristics.

        Uses caching to speed up reconnection.

        Returns:
            True if HID service found and configured
        """
        if not self.peer:
            log.error("Not connected!")
            return False

        # Try cache first
        cache = None
        if self.current_device_address:
            cache = self.gatt_cache.load(self.current_device_address)
            if cache:
                try:
                    self.report_map = bytes.fromhex(cache['report_map'])
                    log.success(f"Using cached report map ({len(self.report_map)} bytes)")

                    if 'device_name' in cache and cache['device_name']:
                        self.device_name = cache['device_name']
                        log.success(f"Using cached device name: {self.device_name}")

                    log.info("Discovering GATT services (using cached data)...")
                except Exception as e:
                    logging.warning(f"Cache corrupt, re-discovering: {e}")
                    cache = None

        if not cache:
            log.info("Discovering GATT services...")

        # Discover services
        await self.peer.discover_services()

        # Read device name if not cached
        if not self.device_name:
            await self._read_device_name()
        else:
            log.info(f"Device Name: {self.device_name} (cached)")

        # Find HID service
        hid_services = [s for s in self.peer.services
                       if s.uuid == GATT_HID_SERVICE]

        if not hid_services:
            log.error("HID service not found!")
            return False

        hid_service = hid_services[0]
        log.success(f"Found HID service: {hid_service.uuid}")

        # Load or discover characteristics
        characteristics_cached = False
        if cache and 'characteristics' in cache:
            characteristics_cached = await self._load_cached_characteristics(
                hid_service, cache
            )

        if not characteristics_cached:
            log.info("Discovering characteristics...")
            await self.peer.discover_characteristics(service=hid_service)
            log.success(f"Discovered {len(hid_service.characteristics)} characteristics")

        # Process characteristics
        report_refs = {}
        characteristics_to_cache = []

        for char in hid_service.characteristics:
            log.detail(f"Characteristic: {char.uuid}")

            # Collect for caching if not already cached
            if not characteristics_cached:
                characteristics_to_cache.append(self._char_to_cache(char))

            if char.uuid == GATT_HID_INFORMATION_CHARACTERISTIC:
                await self._read_hid_info(char)

            elif char.uuid == GATT_HID_REPORT_MAP_CHARACTERISTIC:
                await self._read_report_map(char)

            elif char.uuid == GATT_HID_REPORT_CHARACTERISTIC:
                ref = await self._process_report_characteristic(char, cache)
                if ref:
                    report_refs[str(char.handle)] = ref

        # Update cache
        await self._update_cache(report_refs, characteristics_to_cache)

        return True

    async def subscribe_to_reports(self):
        """Subscribe to HID input report notifications."""
        for report_id, char in self.hid_reports.items():
            try:
                await self.peer.subscribe(char, self._on_hid_report)
                log.success(f"Subscribed to input report {report_id}")
            except Exception as e:
                log.warning(f"Failed to subscribe to report {report_id}: {e}")

    async def run(self, target_address: str):
        """Main connection loop.

        Args:
            target_address: Device address to connect to
        """
        disconnection_event = asyncio.Event()

        def on_disconnection(reason):
            log.error(f"Disconnected: reason={reason}")
            self.button_handler.execute_disconnect_script()
            disconnection_event.set()

        try:
            await self.start()

            if target_address:
                connected = await self.connect(target_address)
                if not connected:
                    return
            else:
                target_address = await self._interactive_scan()
                if not target_address:
                    return
                connected = await self.connect(target_address)
                if not connected:
                    return

            # Set disconnection handler
            self.connection.on('disconnection', on_disconnection)

            # Pair
            if not await self.pair():
                log.error("Pairing failed, exiting")
                return

            # Discover HID service
            if await self.discover_hid_service():
                await self.subscribe_to_reports()

                log.success("\nReceiving HID reports. Press Ctrl+C to exit.")

                try:
                    await disconnection_event.wait()
                    log.warning("\nConnection terminated")
                except asyncio.CancelledError:
                    log.warning("\nConnection cancelled")

        except KeyboardInterrupt:
            log.warning("\nInterrupted by user")
        except asyncio.CancelledError:
            log.warning("\nConnection cancelled")
        except Exception as e:
            log.error(f"Error: {e}")
            logging.exception("Error in run()")
        finally:
            await self.cleanup()
            log.warning("Run method completed, returning to caller")

    async def cleanup(self):
        """Clean up resources."""
        if self.connection:
            try:
                await self.connection.disconnect()
            except Exception:
                pass
        if self.transport:
            await self.transport.close()

    # Private helper methods

    def _on_pairing(self, keys):
        log.success("Pairing successful!")

    def _on_pairing_failure(self, reason):
        log.error(f"Pairing failed: {reason}")

    def _on_hid_report(self, value):
        """Handle incoming HID report."""
        self.button_handler.handle_report(bytes(value))

    async def _read_device_name(self):
        """Read device name from Generic Access Service."""
        try:
            generic_access = [s for s in self.peer.services
                            if s.uuid == GATT_GENERIC_ACCESS_SERVICE]
            if generic_access:
                await self.peer.discover_characteristics(service=generic_access[0])
                name_chars = [c for c in generic_access[0].characteristics
                             if c.uuid == GATT_DEVICE_NAME_CHARACTERISTIC]
                if name_chars:
                    value = await self.peer.read_value(name_chars[0])
                    self.device_name = bytes(value).decode('utf-8', errors='replace')
                    log.info(f"Device Name: {self.device_name}")
        except Exception as e:
            logging.warning(f"Could not read device name: {e}")

    async def _load_cached_characteristics(self, hid_service, cache) -> bool:
        """Load characteristics from cache."""
        log.info("Loading characteristics from cache...")
        try:
            cached_chars = []
            for char_data in cache['characteristics']:
                uuid_str = char_data['uuid']

                # Convert short UUID to full
                if len(uuid_str) == 4:
                    uuid_str = f"0000{uuid_str}-0000-1000-8000-00805F9B34FB"
                elif not uuid_str.startswith('0000'):
                    raise ValueError(f"Invalid UUID format: {uuid_str}")

                char = Characteristic(
                    uuid=UUID(uuid_str),
                    properties=char_data.get('properties', 0),
                    permissions=0,
                    value=b''
                )
                char.handle = char_data['handle']
                char.end_group_handle = char_data['handle'] + 2
                char.service = hid_service

                # Create CCCD descriptor
                cccd = Descriptor(
                    attribute_type=GATT_CCCD,
                    permissions=0,
                    value=b'\x00\x00'
                )
                cccd.handle = char_data['handle'] + 1
                cccd.characteristic = char
                char.descriptors = [cccd]
                char.descriptors_discovered = True

                cached_chars.append(char)

            hid_service.characteristics = cached_chars
            log.success(f"Loaded {len(cached_chars)} characteristics from cache")
            return True

        except Exception as e:
            logging.warning(f"Failed to load cached characteristics: {e}")
            return False

    def _char_to_cache(self, char) -> dict:
        """Convert characteristic to cache format."""
        uuid_hex = char.uuid.to_hex_str()
        if len(uuid_hex) == 4:
            uuid_full = f"0000{uuid_hex}-0000-1000-8000-00805F9B34FB"
        else:
            uuid_full = uuid_hex

        return {
            'uuid': uuid_full,
            'handle': char.handle,
            'properties': getattr(char, 'properties', 0)
        }

    async def _read_hid_info(self, char):
        """Read HID Information characteristic."""
        try:
            value = await self.peer.read_value(char)
            if len(value) >= 4:
                flags = value[3]
                device_type = flags & 0x03
                type_names = {0: 'Unknown', 1: 'Keyboard', 2: 'Mouse', 3: 'Reserved'}
                log.detail(f"HID Information: Device Type = "
                          f"{type_names.get(device_type, 'Unknown')} (0x{device_type:02x})")
        except Exception as e:
            log.detail(f"Failed to read HID Information: {e}")

    async def _read_report_map(self, char):
        """Read HID Report Map characteristic."""
        if self.report_map:
            log.detail(f"Using cached Report Map: {len(self.report_map)} bytes")
            return

        try:
            value = await self.peer.read_value(char)
            self.report_map = bytes(value)
            log.detail(f"Report Map: {len(self.report_map)} bytes")
            log.detail(f"Report Map (hex): {self.report_map.hex()}")

            # Save to cache
            if self.current_device_address:
                cache_data = {
                    'report_map': self.report_map.hex(),
                    'device_name': self.device_name
                }
                self.gatt_cache.save(self.current_device_address, cache_data)
        except Exception as e:
            log.error(f"Failed to read report map: {e}")

    async def _process_report_characteristic(self, char, cache) -> Optional[dict]:
        """Process a Report characteristic."""
        report_id = 0
        report_type = HID_REPORT_TYPE_INPUT
        cached_report_ref = None

        # Check cache for report reference
        if cache and 'report_refs' in cache:
            handle_key = str(char.handle)
            if handle_key in cache['report_refs']:
                cached_report_ref = cache['report_refs'][handle_key]
                report_id = cached_report_ref['id']
                report_type = cached_report_ref['type']
                log.detail(f"Report ID: {report_id}, Type: {report_type} (cached)")

        if not cached_report_ref:
            # Discover and read report reference
            await self.peer.discover_descriptors(characteristic=char)

            for desc in char.descriptors:
                if desc.type == GATT_REPORT_REFERENCE_DESCRIPTOR:
                    try:
                        ref_value = await self.peer.read_value(desc)
                        if len(ref_value) >= 2:
                            report_id = ref_value[0]
                            report_type = ref_value[1]
                    except Exception as e:
                        log.detail(f"Failed to read report reference: {e}")

            log.detail(f"Report ID: {report_id}, Type: {report_type}")

        if report_type == HID_REPORT_TYPE_INPUT:
            self.hid_reports[report_id] = char

        if not cached_report_ref:
            return {'id': report_id, 'type': report_type}

        return None

    async def _update_cache(self, report_refs: dict, characteristics: list):
        """Update GATT cache with new data."""
        if not (report_refs or characteristics) or not self.current_device_address:
            log.success("All data loaded from cache")
            return

        try:
            updates = []
            if report_refs:
                updates.append(f"{len(report_refs)} report references")
            if characteristics:
                updates.append(f"{len(characteristics)} characteristics")
            log.info(f"Updating cache with {', '.join(updates)}...")

            existing = self.gatt_cache.load(self.current_device_address) or {}

            if report_refs:
                if 'report_refs' not in existing:
                    existing['report_refs'] = {}
                existing['report_refs'].update(report_refs)

            if characteristics:
                existing['characteristics'] = characteristics

            if self.report_map:
                existing['report_map'] = self.report_map.hex()
            if self.device_name:
                existing['device_name'] = self.device_name

            self.gatt_cache.save(self.current_device_address, existing)
            log.success("Cache updated successfully")

        except Exception as e:
            logging.warning(f"Failed to update cache: {e}")

    async def _interactive_scan(self) -> Optional[str]:
        """Scan and let user select a device."""
        devices = []
        while not devices:
            devices = await self.scan(duration=10.0, filter_hid=True)
            if not devices:
                log.warning("No HID devices found. Scanning again in 3 seconds...")
                log.info("(Make sure your device is in pairing mode. Press Ctrl+C to exit)")
                await asyncio.sleep(3)

        log.raw("\nSelect device:")
        for i, dev in enumerate(devices):
            log.raw(f"  {i+1}. {dev['name']} ({dev['address']})")

        choice = input("\nEnter number: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]['address']
            else:
                log.raw("Invalid selection")
                return None
        except ValueError:
            log.raw("Invalid input")
            return None
