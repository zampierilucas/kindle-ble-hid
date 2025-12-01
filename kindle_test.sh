#!/bin/bash
# Run PTY experiment on Kindle
# Execute this ON THE KINDLE: ssh root@192.168.0.65 'bash -s' < kindle_test.sh

set -e

echo "=== PTY + hci_uart Experiment on Kindle ==="
echo

# Stop existing bridge
echo "[1] Stopping existing vhci bridge..."
killall vhci_stpbt_bridge 2>/dev/null || true
sleep 2

# Check prerequisites
echo "[2] Checking prerequisites..."
if [ ! -c /dev/stpbt ]; then
    echo "ERROR: /dev/stpbt not found"
    exit 1
fi

if ! lsmod | grep -q hci_uart; then
    echo "WARNING: hci_uart not loaded, trying to load..."
    modprobe hci_uart || echo "Could not load hci_uart"
fi

if ! command -v ldattach &>/dev/null; then
    echo "ERROR: ldattach not found"
    exit 1
fi

echo "Prerequisites OK"
echo

# Start PTY bridge in background
echo "[3] Starting PTY bridge..."
/tmp/pty_stpbt_bridge &
BRIDGE_PID=$!
echo "Bridge PID: $BRIDGE_PID"

# Wait for PTY
sleep 2

if [ ! -L /tmp/bt_pty ]; then
    echo "ERROR: /tmp/bt_pty not created"
    kill $BRIDGE_PID 2>/dev/null
    exit 1
fi

echo "PTY created: /tmp/bt_pty"
echo

# Attach line discipline
echo "[4] Attaching hci_uart (N_HCI=15)..."
ldattach -d -s 115200 15 /tmp/bt_pty
sleep 2

# Check hci0
echo "[5] Checking hci0..."
if hciconfig hci0 2>/dev/null; then
    echo
    echo "SUCCESS: hci0 created!"
    echo
    BUS=$(hciconfig hci0 | grep "Bus:" | awk '{print $2}')
    echo "Bus type: $BUS"
    echo

    if [ "$BUS" = "UART" ]; then
        echo "SUCCESS: Using UART bus (experiment working!)"
    else
        echo "NOTE: Bus is $BUS (expected UART)"
    fi
else
    echo "ERROR: hci0 not created"
    killall ldattach 2>/dev/null
    kill $BRIDGE_PID 2>/dev/null
    exit 1
fi

echo
echo "=== Setup Complete ==="
echo
echo "PTY bridge running (PID: $BRIDGE_PID)"
echo "Next steps:"
echo "  1. hciconfig hci0 up"
echo "  2. hcitool lescan"
echo "  3. Try BLE pairing with bluetoothctl"
echo
echo "To stop:"
echo "  killall ldattach && kill $BRIDGE_PID"
echo
