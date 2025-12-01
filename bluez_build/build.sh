#!/bin/bash
set -e

# BlueZ version
BLUEZ_VERSION="5.50"  # Older version more compatible with old glibc

echo "Building minimal static BlueZ ${BLUEZ_VERSION} for Kindle..."

# Download BlueZ source
if [ ! -f "bluez-${BLUEZ_VERSION}.tar.xz" ]; then
    echo "Downloading BlueZ ${BLUEZ_VERSION}..."
    wget https://www.kernel.org/pub/linux/bluetooth/bluez-${BLUEZ_VERSION}.tar.xz
fi

# Extract
if [ ! -d "bluez-${BLUEZ_VERSION}" ]; then
    echo "Extracting..."
    tar xf bluez-${BLUEZ_VERSION}.tar.xz
fi

cd bluez-${BLUEZ_VERSION}

echo "Build script ready. Will configure and build in container."
