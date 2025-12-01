#!/bin/bash
# Build pty_stpbt_bridge directly on Kindle
# Run this script on the Kindle device

set -e

echo "Building pty_stpbt_bridge on Kindle..."
echo

# Check for gcc
if ! command -v gcc &>/dev/null; then
    echo "ERROR: gcc not found on Kindle"
    echo "This requires a development toolchain on the device"
    exit 1
fi

# Compile
gcc -Wall -O2 -static -o pty_stpbt_bridge_kindle pty_stpbt_bridge.c

echo
echo "Build complete: pty_stpbt_bridge_kindle"
ls -lh pty_stpbt_bridge_kindle
file pty_stpbt_bridge_kindle
