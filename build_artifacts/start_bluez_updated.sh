#!/bin/sh
#
# Start BlueZ Bluetooth stack on Kindle
# This script enables standard BlueZ instead of Amazon's BT stack
#

# Base directory for Bluetooth implementation
BT_DIR="/mnt/us/bluetooth"

# Set up environment
export LD_LIBRARY_PATH="${BT_DIR}/libs"
MUSL_LOADER="${BT_DIR}/bin/ld-musl-armhf.so.1"

echo "Starting BlueZ Bluetooth stack..."

# Load required kernel modules
echo "Loading Bluetooth kernel modules..."
/system/bin/modprobe bluetooth 2>/dev/null || echo "  bluetooth already loaded"
/system/bin/modprobe hci_uart 2>/dev/null || echo "  hci_uart already loaded"
/system/bin/modprobe hci_vhci 2>/dev/null || echo "  hci_vhci already loaded"

# Load MediaTek WMT BT driver (creates /dev/stpbt)
echo "Loading MediaTek WMT BT driver..."
/system/bin/insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko 2>/dev/null || echo "  wmt_cdev_bt already loaded"

# Wait for /dev/stpbt to appear
sleep 1

if [ ! -e /dev/stpbt ]; then
    echo "Error: /dev/stpbt not found!"
    exit 1
fi

echo "/dev/stpbt found"

# Start VHCI bridge (creates virtual HCI interface)
echo "Starting VHCI-stpbt bridge..."
${BT_DIR}/bin/vhci_stpbt_bridge &
BRIDGE_PID=$!
sleep 2

# Bring up HCI interface
echo "Bringing up HCI interface..."
$MUSL_LOADER ${BT_DIR}/bin/hciconfig hci0 up

# Create BlueZ state directory
mkdir -p /var/lib/bluetooth

# Start bluetoothd daemon
echo "Starting bluetoothd..."
$MUSL_LOADER ${BT_DIR}/libexec/bluetooth/bluetoothd &
BLUETOOTHD_PID=$!

sleep 2

# Check status
echo ""
echo "Status:"
$MUSL_LOADER ${BT_DIR}/bin/hciconfig
echo ""
echo "BlueZ is now running!"
echo "Bridge PID: $BRIDGE_PID"
echo "Bluetoothd PID: $BLUETOOTHD_PID"
echo ""
echo "IMPORTANT: BLE HID devices (keyboards/mice) will NOT pair due to kernel limitation."
echo "See /mnt/base-us/BLE_SMP_LIMITATION.md for details."
echo ""
echo "To use bluetoothctl:"
echo "  LD_LIBRARY_PATH=${BT_DIR}/libs ${MUSL_LOADER} ${BT_DIR}/bin/bluetoothctl"
