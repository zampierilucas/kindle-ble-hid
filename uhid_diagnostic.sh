#!/bin/sh
# UHID Diagnostic Script
# Run on Kindle to diagnose input event issues

echo "=============================================="
echo "UHID Diagnostic Report"
echo "=============================================="
echo ""

echo "1. Kernel UHID Support"
echo "----------------------------------------------"
if [ -f /proc/config.gz ]; then
    zcat /proc/config.gz | grep UHID
else
    echo "  /proc/config.gz not found"
    echo "  Trying /boot/config-\$(uname -r)..."
    if [ -f "/boot/config-$(uname -r)" ]; then
        grep UHID "/boot/config-$(uname -r)"
    else
        echo "  Kernel config not available"
    fi
fi
echo ""

echo "2. UHID Device"
echo "----------------------------------------------"
ls -l /dev/uhid 2>/dev/null || echo "  /dev/uhid not found!"
echo ""

echo "3. Input Devices"
echo "----------------------------------------------"
ls -l /dev/input/
echo ""

echo "4. Registered Input Devices (from /proc)"
echo "----------------------------------------------"
if [ -f /proc/bus/input/devices ]; then
    cat /proc/bus/input/devices | grep -E "^(I:|N:|P:|H:)" | sed 's/^/  /'
else
    echo "  /proc/bus/input/devices not found"
fi
echo ""

echo "5. BLE HID Devices (filtering)"
echo "----------------------------------------------"
if [ -f /proc/bus/input/devices ]; then
    # Look for BLE-related devices
    awk '/^$/ {if (found) {print buf; found=0} buf=""}
         {buf=buf $0 "\n"}
         /bumble|BLE HID|ble-hid/ {found=1}
         END {if (found) print buf}' /proc/bus/input/devices | sed 's/^/  /'

    if [ -z "$(grep -i "bumble\|BLE HID\|ble-hid" /proc/bus/input/devices 2>/dev/null)" ]; then
        echo "  No BLE HID devices found"
    fi
else
    echo "  Cannot check"
fi
echo ""

echo "6. Running Processes"
echo "----------------------------------------------"
echo "  BLE HID Daemon:"
ps aux | grep "[b]le_hid_daemon" | sed 's/^/    /'
if [ -z "$(ps aux | grep '[b]le_hid_daemon')" ]; then
    echo "    Not running"
fi

echo ""
echo "  Python processes:"
ps aux | grep "[p]ython.*kindle_ble_hid\|bumble" | sed 's/^/    /'
echo ""

echo "7. Daemon Log (last 15 lines)"
echo "----------------------------------------------"
if [ -f /var/log/ble_hid_daemon.log ]; then
    tail -15 /var/log/ble_hid_daemon.log | sed 's/^/  /'
else
    echo "  Log file not found"
fi
echo ""

echo "8. Recent Kernel Messages (HID/Input related)"
echo "----------------------------------------------"
dmesg | tail -30 | grep -i "input\|hid\|uhid" | sed 's/^/  /'
if [ -z "$(dmesg | tail -30 | grep -i 'input\|hid\|uhid')" ]; then
    echo "  No recent HID/Input messages"
fi
echo ""

echo "9. File Descriptors (UHID)"
echo "----------------------------------------------"
if [ -n "$(ps aux | grep '[b]le_hid_daemon')" ]; then
    PID=$(ps aux | grep '[b]le_hid_daemon' | awk '{print $2}' | head -1)
    echo "  Daemon PID: $PID"
    if [ -d "/proc/$PID/fd" ]; then
        echo "  Open file descriptors to UHID:"
        ls -l "/proc/$PID/fd" 2>/dev/null | grep uhid | sed 's/^/    /' || echo "    None"
    fi
else
    echo "  Daemon not running"
fi
echo ""

echo "10. Quick Test Commands"
echo "----------------------------------------------"
echo "  To monitor UHID events:"
echo "    python3 /tmp/debug_uhid.py"
echo ""
echo "  To test basic UHID functionality:"
echo "    python3 /tmp/test_uhid_simple.py"
echo ""
echo "  To watch input events (replace eventX):"
echo "    evtest /dev/input/eventX"
echo ""
echo "=============================================="
echo "Diagnostic Complete"
echo "=============================================="
