#!/bin/bash
#
# Test script for Kindle power monitoring
#
# Tests:
# 1. Suspend stats availability
# 2. LIPC availability (Kindle only)
# 3. Suspend/resume detection
# 4. Input activity monitoring
#
# Author: Lucas Zampieri <lzampier@redhat.com>
# License: MIT

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Test 1: Check kernel suspend stats support
test_suspend_stats() {
    print_test "Checking /sys/power/suspend_stats/ availability"

    if [ -f /sys/power/suspend_stats/success ]; then
        SUSPEND_COUNT=$(cat /sys/power/suspend_stats/success)
        print_pass "Suspend stats available (success count: $SUSPEND_COUNT)"

        # Check other stats files
        if [ -f /sys/power/suspend_stats/last_hw_sleep ]; then
            LAST_SLEEP=$(cat /sys/power/suspend_stats/last_hw_sleep)
            LAST_SLEEP_SEC=$(echo "scale=2; $LAST_SLEEP / 1000000" | bc 2>/dev/null || echo "N/A")
            print_info "Last hardware sleep: ${LAST_SLEEP_SEC}s"
        fi

        if [ -f /sys/power/suspend_stats/total_hw_sleep ]; then
            TOTAL_SLEEP=$(cat /sys/power/suspend_stats/total_hw_sleep)
            TOTAL_SLEEP_SEC=$(echo "scale=2; $TOTAL_SLEEP / 1000000" | bc 2>/dev/null || echo "N/A")
            print_info "Total hardware sleep: ${TOTAL_SLEEP_SEC}s"
        fi

        if [ -f /sys/power/suspend_stats/fail ]; then
            FAIL_COUNT=$(cat /sys/power/suspend_stats/fail)
            print_info "Failed suspend attempts: $FAIL_COUNT"
        fi
    else
        print_fail "Suspend stats not available (will use uptime discontinuity detection)"
    fi
}

# Test 2: Check LIPC availability (Kindle only)
test_lipc() {
    print_test "Checking LIPC availability"

    if command -v lipc-get-prop &> /dev/null; then
        print_pass "LIPC commands available (running on Kindle)"

        # Try to query power state
        if POWER_STATE=$(lipc-get-prop com.lab126.powerd state 2>/dev/null); then
            print_info "Power state: $POWER_STATE"
        fi

        # Try to query battery
        if BATT_LEVEL=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null); then
            print_info "Battery level: ${BATT_LEVEL}%"
        fi

        # Try to query charging state
        if IS_CHARGING=$(lipc-get-prop com.lab126.powerd isCharging 2>/dev/null); then
            CHARGING_TEXT="No"
            [ "$IS_CHARGING" = "1" ] && CHARGING_TEXT="Yes"
            print_info "Charging: $CHARGING_TEXT"
        fi
    else
        print_info "LIPC not available (not running on Kindle)"
        print_info "This is expected on non-Kindle systems"
    fi
}

# Test 3: Check /proc/uptime for discontinuity detection
test_uptime() {
    print_test "Checking /proc/uptime availability"

    if [ -f /proc/uptime ]; then
        UPTIME=$(cat /proc/uptime | cut -d' ' -f1)
        UPTIME_HOURS=$(echo "scale=2; $UPTIME / 3600" | bc 2>/dev/null || echo "N/A")
        print_pass "Uptime available: ${UPTIME}s (${UPTIME_HOURS}h)"
    else
        print_fail "/proc/uptime not available"
    fi
}

# Test 4: Check /sys/power/state availability
test_power_state() {
    print_test "Checking /sys/power/state availability"

    if [ -f /sys/power/state ]; then
        STATES=$(cat /sys/power/state)
        print_pass "Power states available: $STATES"
    else
        print_fail "/sys/power/state not available"
    fi
}

# Test 5: Check input devices
test_input_devices() {
    print_test "Checking input devices for activity monitoring"

    if [ -d /dev/input ]; then
        EVENT_COUNT=$(ls -1 /dev/input/event* 2>/dev/null | wc -l)
        if [ "$EVENT_COUNT" -gt 0 ]; then
            print_pass "Found $EVENT_COUNT input event devices"
            print_info "Devices: $(ls /dev/input/event* 2>/dev/null | tr '\n' ' ')"
        else
            print_fail "No input event devices found"
        fi
    else
        print_fail "/dev/input directory not found"
    fi
}

# Test 6: Test power monitor module
test_power_monitor_module() {
    print_test "Testing kindle_power_monitor.py module"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MODULE_PATH="$SCRIPT_DIR/bumble_ble_hid/kindle_power_monitor.py"

    if [ ! -f "$MODULE_PATH" ]; then
        print_fail "Module not found at: $MODULE_PATH"
        return
    fi

    # Test module import and basic functionality
    if python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/bumble_ble_hid')
from kindle_power_monitor import KindlePowerMonitor, DeviceState, SuspendMonitor, LIPCMonitor
monitor = KindlePowerMonitor()
print('Module loaded successfully')
print(f'Suspend stats: {monitor.suspend_monitor.supports_suspend_stats}')
print(f'LIPC available: {monitor.lipc_monitor.available}')
" 2>&1; then
        print_pass "Module loads and initializes correctly"
    else
        print_fail "Module failed to load or initialize"
    fi
}

# Test 7: Monitor for suspend/resume (interactive)
test_suspend_resume_monitor() {
    print_test "Interactive suspend/resume monitoring (optional)"

    echo ""
    echo "This test will monitor for suspend/resume events."
    echo "You can:"
    echo "  1. Press Ctrl+C to skip"
    echo "  2. Wait 10 seconds (will exit automatically)"
    echo "  3. Suspend the device manually to test detection"
    echo ""

    if command -v timeout &> /dev/null; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

        # Run monitor for 10 seconds or until Ctrl+C
        if timeout 10 python3 -c "
import sys
import time
sys.path.insert(0, '$SCRIPT_DIR/bumble_ble_hid')
from kindle_power_monitor import SuspendMonitor

monitor = SuspendMonitor()
print(f'Monitoring (10s timeout)...')
print(f'Initial suspend count: {monitor.last_suspend_count}')

for i in range(5):
    time.sleep(2)
    resumed, event = monitor.check_suspend_resume()
    if resumed:
        print(f'RESUME DETECTED!')
        if event:
            print(f'  Duration: {event.suspend_duration:.1f}s')
            print(f'  Count: {event.suspend_count}')
        break
else:
    print('No suspend/resume detected in 10s')
" 2>&1; then
            print_pass "Monitoring completed"
        else
            EXIT_CODE=$?
            if [ $EXIT_CODE -eq 124 ]; then
                print_info "Monitoring timed out (no suspend detected)"
            else
                print_fail "Monitoring failed"
            fi
        fi
    else
        print_info "Skipped (timeout command not available)"
    fi
}

# Test 8: Check Python dependencies
test_python_deps() {
    print_test "Checking Python dependencies"

    if python3 -c "import asyncio" 2>/dev/null; then
        print_pass "asyncio available"
    else
        print_fail "asyncio not available"
    fi

    if python3 -c "import logging" 2>/dev/null; then
        print_pass "logging available"
    else
        print_fail "logging not available"
    fi

    if python3 -c "import select" 2>/dev/null; then
        print_pass "select available"
    else
        print_fail "select not available"
    fi
}

# Main test execution
main() {
    print_header "Kindle Power Monitor Test Suite"

    print_info "System: $(uname -s) $(uname -r)"
    print_info "Python: $(python3 --version 2>&1)"

    # Run all tests
    test_suspend_stats
    test_lipc
    test_uptime
    test_power_state
    test_input_devices
    test_python_deps
    test_power_monitor_module
    test_suspend_resume_monitor

    # Summary
    print_header "Test Summary"
    echo "Total tests: $((TESTS_PASSED + TESTS_FAILED))"
    echo -e "Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Failed: ${RED}${TESTS_FAILED}${NC}"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}All tests passed!${NC}"
        echo "The power monitor should work on this system."
        exit 0
    else
        echo -e "\n${YELLOW}Some tests failed.${NC}"
        echo "The power monitor will still work but some features may be unavailable."
        exit 1
    fi
}

# Run main function
main
