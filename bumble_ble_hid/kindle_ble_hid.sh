#!/bin/sh
# Kindle BLE HID Helper Script
# Usage:
#   ./kindle_ble_hid.sh               - Scan and select device
#   ./kindle_ble_hid.sh DEVICE_ADDR   - Connect to specific device

PYTHON3=/mnt/us/python3.8-kindle/python3-wrapper.sh
SCRIPT_DIR=/mnt/us/bumble_ble_hid

echo "=== Kindle BLE HID Host ==="
echo ""

# Stop any existing Bluetooth processes
echo "Stopping existing Bluetooth processes..."
killall bluetoothd 2>/dev/null || true
killall vhci_stpbt_bridge 2>/dev/null || true
sleep 1

echo ""
echo "Starting BLE HID Host..."
echo "Transport: file:/dev/stpbt"
echo ""

cd "$SCRIPT_DIR"

if [ -n "$1" ]; then
    # Connect to specific address
    exec "$PYTHON3" kindle_ble_hid.py -t file:/dev/stpbt -a "$1"
else
    # Scan and select
    exec "$PYTHON3" kindle_ble_hid.py -t file:/dev/stpbt
fi
