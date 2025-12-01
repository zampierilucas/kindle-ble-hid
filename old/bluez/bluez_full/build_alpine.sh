#!/bin/bash
set -e

BLUEZ_VERSION="5.43"

echo "Building BlueZ with Alpine ARM (musl libc)..."

podman run --rm --platform linux/arm/v7 \
    -v "$(pwd):/build" -w /build \
    docker.io/arm32v7/alpine:3.18 \
    sh -c '
set -e

echo "=== Installing build dependencies ==="
apk add --no-cache \
    build-base \
    linux-headers \
    glib-dev \
    glib-static \
    dbus-dev \
    libical-dev \
    readline-dev \
    readline-static \
    eudev-dev \
    pkgconfig

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
    --disable-midi \
    --disable-manpages

echo ""
echo "=== Building BlueZ ==="
make -j$(nproc) V=1 2>&1 | tail -50

echo ""
echo "=== Installing ==="
make install DESTDIR=/build/install

echo ""
echo "=== Built executables ==="
find /build/install/opt/bluez -type f -executable -exec file {} \; | head -20
'

echo ""
echo "Build complete! Checking results..."
ls -lh install/opt/bluez/bin/ install/opt/bluez/libexec/ 2>/dev/null || true
