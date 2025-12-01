#!/bin/bash
# Quick test script for PTY + hci_uart experiment
# Author: Lucas Zampieri <lzampier@redhat.com>

set -e

PTY_LINK="/tmp/bt_pty"
N_HCI=15

echo "=== PTY + hci_uart Experiment Test Script ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs root privileges for ldattach."
    echo "Run with: sudo $0"
    exit 1
fi

# Step 1: Kill any existing bridges
echo "[1] Stopping existing bridges..."
killall vhci_stpbt_bridge 2>/dev/null || true
killall pty_stpbt_bridge 2>/dev/null || true
killall ldattach 2>/dev/null || true
sleep 1

# Step 2: Check prerequisites
echo "[2] Checking prerequisites..."

if ! lsmod | grep -q hci_uart; then
    echo "ERROR: hci_uart module not loaded"
    echo "Try: modprobe hci_uart"
    exit 1
fi

if ! command -v ldattach &>/dev/null; then
    echo "ERROR: ldattach not found"
    exit 1
fi

if [ ! -c /dev/stpbt ]; then
    echo "ERROR: /dev/stpbt not found"
    exit 1
fi

echo "Prerequisites OK"
echo

# Step 3: Start PTY bridge in background
echo "[3] Starting PTY bridge..."
./pty_stpbt_bridge &
BRIDGE_PID=$!
echo "Bridge PID: $BRIDGE_PID"

# Wait for PTY to be created
for i in {1..10}; do
    if [ -L "$PTY_LINK" ]; then
        break
    fi
    sleep 0.5
done

if [ ! -L "$PTY_LINK" ]; then
    echo "ERROR: PTY link $PTY_LINK not created"
    kill $BRIDGE_PID 2>/dev/null || true
    exit 1
fi

PTY_SLAVE=$(readlink -f "$PTY_LINK")
echo "PTY slave: $PTY_SLAVE"
echo

# Step 4: Attach line discipline
echo "[4] Attaching hci_uart line discipline..."
ldattach -d -s 115200 $N_HCI "$PTY_LINK"
sleep 2

# Step 5: Check if hci0 appeared
echo "[5] Checking for hci0..."
if hciconfig hci0 2>/dev/null | grep -q "Type: Primary"; then
    echo "SUCCESS: hci0 created"
    hciconfig hci0
    echo

    BUS_TYPE=$(hciconfig hci0 | grep "Bus:" | awk '{print $2}')
    echo "Bus type: $BUS_TYPE"

    if [ "$BUS_TYPE" = "UART" ]; then
        echo "SUCCESS: Using UART bus (not VIRTUAL)"
    else
        echo "WARNING: Bus type is $BUS_TYPE (expected UART)"
    fi
else
    echo "ERROR: hci0 not found"
    echo
    echo "Cleanup and exit..."
    killall ldattach 2>/dev/null || true
    kill $BRIDGE_PID 2>/dev/null || true
    exit 1
fi

echo
echo "=== Experiment setup complete ==="
echo
echo "The PTY bridge is running (PID: $BRIDGE_PID)"
echo "To test pairing, run:"
echo "  hciconfig hci0 up"
echo "  hcitool lescan"
echo "  bluetoothctl"
echo
echo "Watch dmesg for SMP errors:"
echo "  dmesg -w | grep -i smp"
echo
echo "To stop the experiment:"
echo "  killall ldattach"
echo "  kill $BRIDGE_PID"
echo
