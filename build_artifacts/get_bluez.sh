#!/bin/bash
# Get prebuilt BlueZ tools for ARM with glibc 2.19+
# We'll extract from Raspberry Pi OS (Raspbian) which targets similar ARM

mkdir -p bluez_arm
cd bluez_arm

# Download Raspbian Stretch packages (glibc 2.24, but might work)
echo "Downloading BlueZ packages..."
wget -q http://archive.raspberrypi.org/debian/pool/main/b/bluez/bluez_5.43-2+rpi2_armhf.deb || \
wget -q http://ftp.debian.org/debian/pool/main/b/bluez/bluez_5.43-2_armhf.deb

if [ -f bluez_*.deb ]; then
    ar x bluez_*.deb
    tar xf data.tar.xz
    echo "Extracted BlueZ tools:"
    find . -name "bluetoothctl" -o -name "btmgmt" -o -name "bluetoothd" | head -5
fi
