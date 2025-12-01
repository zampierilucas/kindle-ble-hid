#!/bin/bash
# Simple test - new version doesn't need ldattach

echo "=== PTY + hci_uart Experiment (Self-contained) ==="
echo

# Stop existing bridge
echo "[1] Stopping existing bridges..."
killall vhci_stpbt_bridge 2>/dev/null || true
killall pty_stpbt_bridge 2>/dev/null || true
sleep 2

# Check hci_uart module
echo "[2] Checking hci_uart module..."
if ! lsmod | grep -q hci_uart; then
    echo "Loading hci_uart module..."
    modprobe hci_uart || echo "WARNING: Could not load hci_uart"
fi

echo "[3] Starting PTY bridge (with automatic line discipline attachment)..."
echo
/tmp/pty_stpbt_bridge &
BRIDGE_PID=$!

echo
echo "Bridge PID: $BRIDGE_PID"
echo "Waiting for hci0 to appear..."
sleep 3

# Check hci0
echo
echo "[4] Checking hci0..."
if hciconfig hci0 2>/dev/null; then
    echo
    echo "=== SUCCESS: hci0 created! ==="
    echo
    BUS=$(hciconfig hci0 | grep "Bus:" | awk '{print $2}')
    echo "Bus type: $BUS"

    if [ "$BUS" = "UART" ]; then
        echo
        echo "*** EXCELLENT: Using UART bus! ***"
        echo "This is different from VHCI - experiment working!"
    else
        echo
        echo "Bus is: $BUS"
    fi

    echo
    echo "Now test with:"
    echo "  hciconfig hci0 up"
    echo "  hcitool lescan"
    echo
    echo "To stop: kill $BRIDGE_PID"
else
    echo "ERROR: hci0 not found"
    echo
    echo "Check dmesg for errors:"
    dmesg | tail -20
    kill $BRIDGE_PID 2>/dev/null
fi
