#!/bin/sh
# Verification script to check if ble-hid service is set up for auto-start
# Run this on the Kindle device

echo "========================================="
echo "BLE HID Service Auto-Start Verification"
echo "========================================="
echo ""

# Check if init script is installed
echo "1. Checking if /etc/init.d/ble-hid exists..."
if [ -f /etc/init.d/ble-hid ]; then
    echo "   [OK] Init script is installed"
    ls -la /etc/init.d/ble-hid
else
    echo "   [MISSING] Init script NOT installed at /etc/init.d/ble-hid"
fi
echo ""

# Check if script is executable
echo "2. Checking if init script is executable..."
if [ -x /etc/init.d/ble-hid ]; then
    echo "   [OK] Init script is executable"
else
    echo "   [WARNING] Init script is NOT executable"
fi
echo ""

# Check for runlevel symlinks
echo "3. Checking for auto-start symlinks in runlevel directories..."
FOUND=0
for rcdir in /etc/rc*.d; do
    if [ -d "$rcdir" ]; then
        LINKS=$(ls -1 "$rcdir"/*ble-hid* 2>/dev/null)
        if [ -n "$LINKS" ]; then
            echo "   Found in $rcdir:"
            ls -la "$rcdir"/*ble-hid*
            FOUND=1
        fi
    fi
done

if [ $FOUND -eq 0 ]; then
    echo "   [MISSING] No auto-start symlinks found"
    echo "   Service will NOT start automatically on boot"
else
    echo "   [OK] Auto-start symlinks found"
fi
echo ""

# Check current service status
echo "4. Checking current service status..."
if [ -f /etc/init.d/ble-hid ]; then
    /etc/init.d/ble-hid status
else
    echo "   Cannot check status - init script not installed"
fi
echo ""

# Summary
echo "========================================="
echo "Summary:"
echo "========================================="
if [ -f /etc/init.d/ble-hid ] && [ -x /etc/init.d/ble-hid ] && [ $FOUND -eq 1 ]; then
    echo "[OK] Service is properly configured for auto-start"
else
    echo "[ACTION NEEDED] Service is NOT configured for auto-start"
    echo ""
    echo "To enable auto-start, run:"
    echo "  cp /mnt/us/bumble_ble_hid/ble-hid.init /etc/init.d/ble-hid"
    echo "  chmod +x /etc/init.d/ble-hid"
    echo "  update-rc.d ble-hid defaults"
fi
echo ""
