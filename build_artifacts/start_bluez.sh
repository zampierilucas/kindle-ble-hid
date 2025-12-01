#!/bin/sh
#
# Start BlueZ Bluetooth stack on Kindle
# This script enables standard BlueZ instead of Amazon's BT stack
#

# Set up environment
export LD_LIBRARY_PATH=/mnt/us/libs
MUSL_LOADER=/mnt/us/ld-musl-armhf.so.1

echo "Starting BlueZ Bluetooth stack..."

# Load required kernel modules
echo "Loading Bluetooth kernel modules..."
modprobe bluetooth
modprobe hci_uart
modprobe hci_vhci

# Load MediaTek WMT BT driver (creates /dev/stpbt)
echo "Loading MediaTek WMT BT driver..."
insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko

# Wait for /dev/stpbt to appear
sleep 1

if [ ! -e /dev/stpbt ]; then
    echo "Error: /dev/stpbt not found!"
    exit 1
fi

echo "/dev/stpbt found"

# Start VHCI bridge (creates virtual HCI interface)
echo "Starting VHCI-stpbt bridge..."
/mnt/us/vhci_stpbt_bridge &
BRIDGE_PID=$!
sleep 2

# Bring up HCI interface
echo "Bringing up HCI interface..."
$MUSL_LOADER /mnt/us/bin/hciconfig hci0 up

# Create BlueZ state directory
mkdir -p /var/lib/bluetooth

# Start bluetoothd daemon
echo "Starting bluetoothd..."
$MUSL_LOADER /mnt/us/libexec/bluetooth/bluetoothd &
BLUETOOTHD_PID=$!

sleep 2

# Check status
echo ""
echo "Status:"
$MUSL_LOADER /mnt/us/bin/hciconfig
echo ""
echo "BlueZ is now running!"
echo "Bridge PID: $BRIDGE_PID"
echo "Bluetoothd PID: $BLUETOOTHD_PID"
echo ""
echo "To pair a device:"
echo "  LD_LIBRARY_PATH=/mnt/us/libs /mnt/us/ld-musl-armhf.so.1 /mnt/us/bin/bluetoothctl"
echo "  Then: power on, agent on, default-agent, scan on, pair <MAC>, connect <MAC>"
