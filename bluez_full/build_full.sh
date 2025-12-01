#!/bin/bash
set -e

# Full BlueZ build for Kindle (glibc 2.20, ARMv7)
# Using Debian Stretch ARM container (glibc 2.24 - close enough)

BLUEZ_VERSION="5.43"
PREFIX="/opt/bluez"
NCPU=$(nproc)

echo "=== Full BlueZ ${BLUEZ_VERSION} Build for Kindle ==="
echo "Target: ARMv7, glibc 2.20+"
echo "Build cores: ${NCPU}"
echo ""

# Download sources
echo "Downloading BlueZ ${BLUEZ_VERSION}..."
if [ ! -f "bluez-${BLUEZ_VERSION}.tar.xz" ]; then
    wget -q "https://www.kernel.org/pub/linux/bluetooth/bluez-${BLUEZ_VERSION}.tar.xz"
    tar xf bluez-${BLUEZ_VERSION}.tar.xz
fi

echo "Source downloaded and extracted."
echo ""
echo "Next: Will build in ARM container with dependencies"
