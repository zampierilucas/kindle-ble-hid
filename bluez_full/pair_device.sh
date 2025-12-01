#!/bin/bash
# Script to pair BLE device using bluetoothctl

DEVICE_MAC="5C:2B:3E:50:4F:04"
DEVICE_PATH="/org/bluez/hci0/dev_5C_2B_3E_50_4F_04"

cd /mnt/us
export LD_LIBRARY_PATH=/mnt/us/libs

echo "Starting scan..."
echo -e "scan on\n" | timeout 15 ./ld-musl-armhf.so.1 ./bin/bluetoothctl

sleep 5

echo "Device should be discovered. Attempting to pair..."
echo -e "pair $DEVICE_MAC\n" | timeout 30 ./ld-musl-armhf.so.1 ./bin/bluetoothctl

sleep 2

echo "Trusting device..."
echo -e "trust $DEVICE_MAC\n" | ./ld-musl-armhf.so.1 ./bin/bluetoothctl

sleep 1

echo "Connecting to device..."
echo -e "connect $DEVICE_MAC\n" | timeout 20 ./ld-musl-armhf.so.1 ./bin/bluetoothctl

sleep 2

echo "Checking connection status..."
echo -e "info $DEVICE_MAC\n" | ./ld-musl-armhf.so.1 ./bin/bluetoothctl

echo ""
echo "Done! Check /dev/input for new device."
