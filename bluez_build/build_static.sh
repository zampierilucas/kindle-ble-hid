#!/bin/bash
set -e

BLUEZ_VERSION="5.50"
BUILD_DIR="/work"
INSTALL_DIR="/work/install"
BLUEZ_SRC="${BUILD_DIR}/bluez-${BLUEZ_VERSION}"

cd ${BLUEZ_SRC}

# Configure with minimal options
# Disable most features to reduce dependencies
./configure \
    --prefix=${INSTALL_DIR} \
    --host=arm-linux-musleabihf \
    --disable-systemd \
    --disable-udev \
    --disable-cups \
    --disable-obex \
    --disable-client \
    --disable-mesh \
    --disable-midi \
    --disable-tools \
    --enable-library \
    --enable-deprecated \
    --enable-experimental \
    LDFLAGS="-static" \
    CFLAGS="-Os -static"

# Build
make -j$(nproc)

# Create output directory
mkdir -p ${BUILD_DIR}/output

# Copy binaries
if [ -f "src/bluetoothd" ]; then
    cp src/bluetoothd ${BUILD_DIR}/output/
    echo "Built: bluetoothd"
fi

if [ -f "client/bluetoothctl" ]; then
    cp client/bluetoothctl ${BUILD_DIR}/output/
    echo "Built: bluetoothctl"
fi

if [ -f "tools/btmgmt" ]; then
    cp tools/btmgmt ${BUILD_DIR}/output/
    echo "Built: btmgmt"
fi

ls -la ${BUILD_DIR}/output/
