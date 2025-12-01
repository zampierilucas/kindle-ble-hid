#!/bin/bash
set -e

BLUEZ_VERSION="5.43"
NCPU=$(nproc)

echo "Building BlueZ in ARM Debian Stretch container..."

# Use Debian Stretch (glibc 2.24) for ARMv7
podman run --rm --platform linux/arm/v7 \
    -v "$(pwd):/build" -w /build \
    docker.io/arm32v7/debian:stretch \
    bash -c '
set -e

echo "=== Installing build dependencies ==="
apt-get update -qq
apt-get install -y -qq \
    build-essential \
    libglib2.0-dev \
    libdbus-1-dev \
    libical-dev \
    libreadline-dev \
    libudev-dev \
    pkg-config \
    wget > /dev/null 2>&1

echo ""
echo "=== Configuring BlueZ '"${BLUEZ_VERSION}"' ==="
cd bluez-'"${BLUEZ_VERSION}"'

./configure \
    --prefix=/opt/bluez \
    --enable-tools \
    --enable-deprecated \
    --enable-experimental \
    --disable-systemd \
    --disable-cups \
    --disable-obex \
    --disable-mesh \
    --disable-midi

echo ""
echo "=== Building BlueZ (this will take 5-10 minutes) ==="
make -j'"${NCPU}"'

echo ""
echo "=== Installing to /opt/bluez ==="
make install DESTDIR=/build/install

echo ""
echo "=== Build complete! ==="
ls -lh /build/install/opt/bluez/bin/ 2>/dev/null || true
ls -lh /build/install/opt/bluez/libexec/bluetooth/ 2>/dev/null || true
'

echo ""
echo "Build finished! Checking output..."
ls -la install/opt/bluez/bin/ 2>/dev/null || echo "No bin directory"
ls -la install/opt/bluez/libexec/bluetooth/ 2>/dev/null || echo "No libexec directory"
