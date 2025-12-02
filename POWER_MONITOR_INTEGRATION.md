# Kindle Power Monitor Integration Guide

Integration guide for adding proper idle and suspend detection to the BLE HID daemon.

## Overview

The `kindle_power_monitor.py` module provides proper system-level idle detection by monitoring:
- **Suspend/resume cycles** via `/sys/power/suspend_stats/`
- **LIPC power events** (Kindle-specific)
- **Input activity** (integrated with existing monitoring)

This replaces the current assumption-based idle detection that only monitors input events.

## Current Implementation (ble_hid_daemon.py)

Current idle detection (lines 67-118):
```python
def monitor_activity(self):
    """Monitor input devices for activity"""
    # Opens /dev/input/event* and uses select()
    # Updates self.last_activity_time

def is_kindle_active(self):
    """Check if Kindle is active based on recent input"""
    return (time.time() - self.last_activity_time) < self.IDLE_THRESHOLD
```

**Limitations:**
- Cannot detect system suspend/resume
- Assumes "no input" means "idle" (but device might be suspended)
- BLE connections lost during suspend are not properly detected
- Reconnection logic doesn't distinguish between idle and suspended

## Proposed Integration

### Step 1: Import Power Monitor

Add to `ble_hid_daemon.py`:
```python
from kindle_power_monitor import (
    KindlePowerMonitor,
    DeviceState,
    SuspendEvent
)
```

### Step 2: Initialize in BLEHIDDaemon.__init__()

Replace or augment existing activity monitoring:
```python
class BLEHIDDaemon:
    def __init__(self, config_file, log_file=None):
        # ... existing code ...

        # Initialize power monitor
        self.power_monitor = KindlePowerMonitor(
            idle_threshold=self.IDLE_THRESHOLD,
            deep_idle_threshold=self.IDLE_THRESHOLD * 5
        )

        # Register our activity checker with the power monitor
        self.power_monitor.set_activity_checker(self._check_input_activity)

        # Track suspend state
        self.was_suspended = False
```

### Step 3: Refactor Activity Monitoring

Convert `is_kindle_active()` to return activity info:
```python
def _check_input_activity(self) -> Tuple[bool, float]:
    """
    Check input activity for power monitor.

    Returns:
        (has_activity, idle_seconds)
    """
    idle_seconds = time.time() - self.last_activity_time
    has_activity = idle_seconds < 1.0  # Active in last second
    return has_activity, idle_seconds
```

### Step 4: Update Main Loop

Replace activity-based logic with state-based logic:
```python
async def run(self):
    """Main daemon loop"""
    while True:
        # Get current device state
        device_state = self.power_monitor.get_device_state()

        # Handle suspend/resume
        if device_state == DeviceState.RESUMED:
            logging.info("System resumed from suspend")
            event = self.power_monitor.last_resume_event
            if event:
                logging.info(f"Slept for {event.suspend_duration:.1f}s")

            # Reinitialize all connections after suspend
            await self._handle_resume()
            self.power_monitor.mark_resume_handled()
            self.was_suspended = False
            continue

        # Determine reconnect delay based on state
        if device_state == DeviceState.ACTIVE:
            delay = self.RECONNECT_DELAY_ACTIVE
        elif device_state == DeviceState.IDLE:
            delay = self.RECONNECT_DELAY_IDLE
        else:  # DEEP_IDLE
            delay = self.RECONNECT_DELAY_IDLE * 2

        # Try to connect/maintain connections
        for address in self.device_addresses:
            if address not in self.active_hosts or not self.active_hosts[address].connected:
                await self._connect_device(address)

        # Monitor activity (keeps last_activity_time updated)
        self.monitor_activity()

        await asyncio.sleep(delay)
```

### Step 5: Add Resume Handler

New method to reinitialize after suspend:
```python
async def _handle_resume(self):
    """Handle system resume from suspend"""
    logging.info("Reinitializing Bumble hosts after resume...")

    # Stop all existing connections
    for address, host in list(self.active_hosts.items()):
        try:
            await host.disconnect()
        except Exception as e:
            logging.warning(f"Error disconnecting {address}: {e}")

    # Clear active hosts
    self.active_hosts.clear()

    # Optionally: Reload GATT cache as it might be stale
    for address in self.device_addresses:
        cache_file = f'/tmp/gatt_cache_{address.replace(":", "_")}.json'
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                logging.info(f"Cleared GATT cache for {address}")
            except Exception as e:
                logging.warning(f"Failed to clear cache: {e}")

    # Reset activity timestamp to prevent immediate idle state
    self.last_activity_time = time.time()

    # Connections will be re-established in next main loop iteration
```

## Configuration

Add new constants to `ble_hid_daemon.py`:
```python
# Activity thresholds
IDLE_THRESHOLD = 60          # 60s - existing
DEEP_IDLE_THRESHOLD = 300    # 5m - new

# Reconnect delays
RECONNECT_DELAY_ACTIVE = 3        # existing
RECONNECT_DELAY_IDLE = 30         # existing
RECONNECT_DELAY_DEEP_IDLE = 60    # new - very slow reconnect
```

## Testing

### Test Script Usage

```bash
# Test suspend detection
python3 bumble_ble_hid/kindle_power_monitor.py

# Test with daemon (dry-run mode recommended first)
python3 bumble_ble_hid/ble_hid_daemon.py --config devices.conf --log-file /tmp/test.log
```

### Manual Testing Procedure

1. **Start daemon with logging:**
   ```bash
   python3 bumble_ble_hid/ble_hid_daemon.py --config devices.conf --log-file /tmp/ble_daemon.log
   tail -f /tmp/ble_daemon.log
   ```

2. **Test activity detection:**
   - Touch screen / press buttons
   - Wait 60s without input
   - Verify log shows state transitions: ACTIVE → IDLE → DEEP_IDLE

3. **Test suspend/resume:**
   - Trigger Kindle suspend (wait for screensaver, then wait for auto-suspend)
   - Or manually: `echo mem > /sys/power/state` (requires root)
   - Wait 30+ seconds
   - Wake device
   - Verify log shows "RESUMED" state and reinitialize

4. **Test BLE reconnection:**
   - Verify BLE device reconnects faster when active
   - Verify slower reconnects when idle
   - Verify immediate reconnect after resume

### Automated Test Script

See `test_power_monitor.sh` for automated testing.

## LIPC Integration (Kindle-Specific)

If running on actual Kindle with LIPC available:

### Prevent Sleep During Active BLE Use

```python
def on_device_connected(self, address):
    """Called when BLE device connects"""
    # Prevent sleep while device is connected
    if len(self.active_hosts) == 1:  # First device
        self.power_monitor.prevent_sleep(True)
        logging.info("Preventing device sleep (BLE device active)")

def on_device_disconnected(self, address):
    """Called when BLE device disconnects"""
    # Allow sleep when no devices connected
    if len(self.active_hosts) == 0:  # Last device
        self.power_monitor.prevent_sleep(False)
        logging.info("Allowing device sleep (no BLE devices)")
```

### Monitor Battery State

```python
# Periodically log battery info
battery_info = self.power_monitor.get_battery_info()
if battery_info['level'] is not None:
    logging.info(f"Battery: {battery_info['level']}% "
                f"(charging: {battery_info['charging']})")

    # Optionally: Reduce BLE activity on low battery
    if battery_info['level'] < 10 and not battery_info['charging']:
        logging.warning("Low battery, reducing BLE reconnect frequency")
        # Increase delays...
```

## Migration Path

### Phase 1: Add Monitoring (Non-Breaking)
1. Add `kindle_power_monitor.py` to project
2. Import and initialize in daemon (keep existing logic)
3. Log device states for observation
4. No behavior changes yet

### Phase 2: Integrate Suspend Detection
1. Add `_handle_resume()` method
2. Update main loop to detect RESUMED state
3. Reinitialize Bumble hosts on resume
4. Test thoroughly

### Phase 3: Refine Reconnect Logic
1. Use state-based reconnect delays
2. Distinguish IDLE vs DEEP_IDLE
3. Optimize for battery life

### Phase 4: LIPC Integration (Optional)
1. Add sleep prevention during active use
2. Add battery monitoring
3. Kindle-specific optimizations

## Performance Considerations

### Overhead
- **SuspendMonitor**: ~0.1ms per check (reads 2 files from /sys)
- **LIPCMonitor**: ~10-50ms per query (subprocess call)
- **Recommendation**: Check suspend state every 2-5 seconds (current loop delay)

### Memory
- **Power monitor**: <1KB overhead
- **No additional threads**: Uses existing event loop

### Battery Impact
- **Minimal**: Only adds file reads, no additional I/O
- **Benefit**: Proper suspend detection allows better power management

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or in daemon:
logger = logging.getLogger('kindle_power_monitor')
logger.setLevel(logging.DEBUG)
```

### Check Kernel Support

```bash
# Verify suspend_stats available
ls -la /sys/power/suspend_stats/

# Check current values
cat /sys/power/suspend_stats/success
cat /sys/power/suspend_stats/last_hw_sleep

# Test manual suspend (requires root)
echo mem > /sys/power/state

# Check dmesg for suspend/resume
dmesg | grep -i suspend | tail -20
```

### LIPC Commands (Kindle Only)

```bash
# Check if LIPC available
which lipc-get-prop

# Query power state
lipc-get-prop com.lab126.powerd state

# Monitor power events
lipc-wait-event com.lab126.powerd resuming
```

## Known Limitations

1. **Suspend stats not available on all kernels**
   - Fallback: uptime discontinuity detection
   - Less accurate but functional

2. **LIPC only on Kindle devices**
   - Gracefully degrades on non-Kindle systems
   - Standard Linux interfaces still work

3. **Bluetooth stack behavior during suspend**
   - Kernel BT stack state is lost
   - Bumble state in Python might be stale
   - Solution: Full reinitialization after resume

4. **Race conditions**
   - Resume detection has ~2s latency
   - Existing reconnect loop might attempt connection before resume detected
   - Solution: Mark connections as failed quickly on resume

## Future Enhancements

### Possible Improvements

1. **Async/await integration**
   - Make power monitor async-compatible
   - Use asyncio for LIPC queries

2. **Event-driven architecture**
   - Use inotify on /sys/power/suspend_stats/
   - Register callbacks for state changes
   - Eliminate polling

3. **Predictive reconnection**
   - Learn user's usage patterns
   - Predict wake-up times
   - Pre-connect just before expected activity

4. **KOReader integration**
   - Detect if KOReader is running
   - Use KOReader-specific idle detection
   - Different policies for KOReader vs system UI

5. **Advanced battery optimization**
   - Dynamic delay adjustment based on battery level
   - Disable BLE below threshold
   - Hysteresis to prevent thrashing

## Support

For issues or questions:
- Check daemon logs: `/tmp/ble_hid_daemon.log`
- Check kernel logs: `dmesg | grep -i suspend`
- File issues: [Your issue tracker]

## References

- Kernel power management: `Documentation/power/` in Linux source
- LIPC documentation: [Kindle development forums]
- Bumble documentation: https://github.com/google/bumble
