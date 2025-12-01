#!/bin/bash
set -e

BLUEZ_VER="5.43"

# Download if needed
if [ ! -f "bluez-${BLUEZ_VER}.tar.xz" ]; then
    wget "https://www.kernel.org/pub/linux/bluetooth/bluez-${BLUEZ_VER}.tar.xz"
    tar xf bluez-${BLUEZ_VER}.tar.xz
fi

cd bluez-${BLUEZ_VER}

# Build just the tools we need without full daemon
# This will use the system's toolchain
CC=gcc \
CFLAGS="-Os" \
./configure \
    --prefix=/tmp/bluez-install \
    --disable-systemd \
    --disable-udev \
    --disable-cups \
    --disable-obex \
    --disable-mesh \
    --disable-midi \
    --enable-tools \
    --enable-deprecated \
    --enable-experimental

make -j$(nproc) tools/btmgmt attrib/gatttool

ls -la tools/btmgmt attrib/gatttool 2>&1 || echo "Build check..."
