# Bumble BLE HID Implementation Fixes

## Date
December 1, 2025

## Problem
The `/mnt/us/bumble_ble_hid/kindle_ble_hid.py` implementation was broken due to API incompatibilities with Bumble version 0.0.200.

## Fixed Issues

### 1. Device Initialization API (Line ~245)
**Old (Broken):**
```python
self.device = Device(
    name='Kindle-BLE-HID',
    address=Address('F0:F0:F0:F0:F0:F0'),
    host=self.transport.source,
)
self.device.host.set_packet_sink(self.transport.sink)
```

**New (Fixed):**
```python
self.device = Device.with_hci(
    'Kindle-BLE-HID',
    'F0:F0:F0:F0:F0:F0',
    self.transport.source,
    self.transport.sink
)
```

**Reason:** Bumble 0.0.200 uses `Device.with_hci()` factory method for creating devices with HCI transport.

### 2. AdvertisingData Access (Lines ~265-280)
**Old (Broken):**
```python
name = advertisement.data.get(AdvertisingData.COMPLETE_LOCAL_NAME) or \
       advertisement.data.get(AdvertisingData.SHORTENED_LOCAL_NAME) or \
       str(addr)

services = advertisement.data.get(
    AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS, []
) + advertisement.data.get(
    AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS, []
)
```

**New (Fixed):**
```python
name = 'Unknown'
if hasattr(advertisement, 'data') and advertisement.data:
    for ad_type, ad_data in advertisement.data:
        if ad_type == AdvertisingData.COMPLETE_LOCAL_NAME or \
           ad_type == AdvertisingData.SHORTENED_LOCAL_NAME:
            try:
                name = ad_data.decode('utf-8', errors='replace')
            except:
                name = str(ad_data)
            break

is_hid = False
if hasattr(advertisement, 'data') and advertisement.data:
    for ad_type, ad_data in advertisement.data:
        if ad_type == AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS or \
           ad_type == AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS:
            for i in range(0, len(ad_data), 2):
                uuid_bytes = ad_data[i:i+2]
                if len(uuid_bytes) == 2:
                    uuid_val = int.from_bytes(uuid_bytes, 'little')
                    if uuid_val == 0x1812:  # HID service
                        is_hid = True
                        break
```

**Reason:** In Bumble 0.0.200, `advertisement.data` is an iterable of (ad_type, ad_data) tuples, not a dict-like object. Service UUIDs are stored as raw bytes in little-endian format that need to be parsed manually.

### 3. Scanning API (Line ~304)
**Old (Broken):**
```python
await self.device.start_scanning()
```

**New (Fixed):**
```python
await self.device.start_scanning(filter_duplicates=True)
```

**Reason:** Added explicit `filter_duplicates=True` parameter to prevent duplicate advertisements from showing up multiple times, along with manual deduplication in the callback using `seen_addresses` set.

### 4. Wait for Termination (Line ~492)
**Old (Broken):**
```python
await self.transport.source.terminated
```

**New (Fixed):**
```python
await self.transport.source.wait_for_termination()
```

**Reason:** Bumble 0.0.200 uses `wait_for_termination()` method instead of awaiting the `terminated` attribute directly.

## Testing Status

- Import test: PASSED
- Script syntax: VALID
- Runtime test: PENDING (requires actual BLE HID device)

## Files Changed

- `/mnt/us/bumble_ble_hid/kindle_ble_hid.py` - Main implementation (backed up to `kindle_ble_hid.py.broken`)

## Next Steps

1. Test scanning functionality with the Kindle
2. Test connection to a BLE HID device (keyboard, mouse, or game controller)
3. Verify pairing works correctly
4. Verify HID report injection via UHID

## Bumble Version
- Installed: 0.0.200
- Location: `/mnt/us/python3.8-kindle/bumble/`

## Author
Lucas Zampieri <lzampier@redhat.com>
