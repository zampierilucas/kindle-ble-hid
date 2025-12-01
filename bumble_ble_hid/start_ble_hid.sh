#!/bin/bash
# Start BLE HID Host on Kindle
# This script uses Google Bumble to connect to BLE HID devices
# bypassing the kernel SMP bug with the VHCI approach

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUETOOTH_DIR="/mnt/us/bluetooth"

echo "=== Kindle BLE HID Host ==="
echo ""

# Check if we're on the Kindle
if [ -e /dev/stpbt ]; then
    TRANSPORT="file:/dev/stpbt"
    echo "Detected Kindle device, using /dev/stpbt"
else
    echo "Not on Kindle, using default transport"
    TRANSPORT="${1:-usb:0}"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3 on the Kindle"
    exit 1
fi

# Check for bumble
if ! python3 -c "import bumble" 2>/dev/null; then
    echo "ERROR: Bumble not installed!"
    echo "Install with: pip3 install bumble"
    exit 1
fi

# Stop any existing BlueZ/bridge processes
echo "Stopping existing Bluetooth processes..."
killall bluetoothd 2>/dev/null || true
killall vhci_stpbt_bridge 2>/dev/null || true
killall pty_stpbt_bridge 2>/dev/null || true
sleep 1

# Run the BLE HID host
echo ""
echo "Starting BLE HID Host..."
echo "Transport: $TRANSPORT"
echo ""

cd "$SCRIPT_DIR"
exec python3 kindle_ble_hid.py \
    --transport "$TRANSPORT" \
    --config device_config.json \
    "$@"
