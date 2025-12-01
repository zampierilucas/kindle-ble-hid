#!/bin/bash
# Build ARM musl binary using Docker Alpine
set -e

echo "Building pty_stpbt_bridge for ARM with musl..."

# Use Alpine ARM container for musl-based static build
docker run --rm --platform linux/arm/v7 -v "$PWD:/work" -w /work \
    arm32v7/alpine:3.19 \
    sh -c '
    apk add --no-cache gcc musl-dev make
    gcc -Wall -Wextra -O2 -static \
        -march=armv7-a -mtune=cortex-a53 \
        -o pty_stpbt_bridge_musl \
        src/pty_stpbt_bridge_ldisc.c
    echo
    echo "Build complete!"
    ls -lh pty_stpbt_bridge_musl
    file pty_stpbt_bridge_musl
'

echo
echo "ARM musl binary ready: pty_stpbt_bridge_musl"
