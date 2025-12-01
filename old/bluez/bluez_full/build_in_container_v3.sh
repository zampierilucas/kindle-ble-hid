#!/bin/bash
set -e

BLUEZ_VERSION="5.43"
NCPU=$(nproc)

echo "Building BlueZ in ARM Debian Bullseye container..."

podman run --rm --platform linux/arm/v7 \
    -v "$(pwd):/build" -w /build \
    docker.io/arm32v7/debian:bullseye \
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
    wget 2>&1 | tail -5

echo ""
echo "=== Configuring BlueZ '"${BLUEZ_VERSION}"' ==="
cd bluez-'"${BLUEZ_VERSION}"'

LDFLAGS="-Wl,-rpath,/opt/bluez/lib" \
./configure \
    --prefix=/opt/bluez \
    --enable-tools \
    --enable-deprecated \
    --enable-experimental \
    --disable-systemd \
    --disable-cups \
    --disable-obex \
    --disable-mesh \
    --disable-midi 2>&1 | tail -20

echo ""
echo "=== Building BlueZ (this will take 5-10 minutes) ==="
make -j'"${NCPU}"' 2>&1 | grep -E "(CC|CCLD|error|warning:)" || true

echo ""
echo "=== Installing to /opt/bluez ==="
make install DESTDIR=/build/install 2>&1 | tail -10

echo ""
echo "=== Copying required libraries ==="
mkdir -p /build/install/opt/bluez/lib
for lib in libglib-2.0.so.0 libdbus-1.so.3 libical.so.3 libreadline.so.7; do
    if [ -f "/usr/lib/arm-linux-gnueabihf/$lib" ]; then
        cp -L "/usr/lib/arm-linux-gnueabihf/$lib" /build/install/opt/bluez/lib/ || true
    fi
done

echo ""
echo "=== Build complete! ==="
find /build/install/opt/bluez -type f -executable | head -20
echo ""
echo "Libraries:"
ls -lh /build/install/opt/bluez/lib/ 2>/dev/null || true
'

echo ""
echo "Build finished! Checking output..."
find install/opt/bluez -type f | head -30
