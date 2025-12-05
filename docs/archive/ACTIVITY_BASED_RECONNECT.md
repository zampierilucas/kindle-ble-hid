# Activity-Based Reconnection System

The BLE HID daemon now uses intelligent reconnection delays based on Kindle user activity instead of exponential backoff.

## How It Works

### Activity Detection

The daemon monitors all `/dev/input/event*` devices for user input:
- Keyboard presses
- Button presses
- Touch events (if applicable)
- Any other input device activity

When any input event is detected, the Kindle is considered "active" for the next 60 seconds.

### Reconnection Delays

**When Kindle is ACTIVE** (user interacting within last 60 seconds):
- Reconnection delay: **3 seconds**
- Fast reconnection for immediate use when you turn on your BLE device

**When Kindle is IDLE** (no interaction for 60+ seconds):
- Reconnection delay: **30 seconds**
- Battery-saving slow reconnection when Kindle is not in use

### Connection Timeout

Each connection attempt times out after **10 seconds** instead of the previous 30 seconds, saving battery on failed attempts.

## Configuration

Constants in `ble_hid_daemon.py`:

```python
RECONNECT_DELAY_ACTIVE = 3   # seconds - fast retry when active
RECONNECT_DELAY_IDLE = 30    # seconds - slow retry when idle
CONNECTION_TIMEOUT = 10      # seconds - connection attempt timeout
IDLE_THRESHOLD = 60          # seconds - idle after 60s of no input
```

## Example Behavior

### Scenario 1: You're actively using the Kindle
1. BLE mouse disconnects (battery dies)
2. You replace batteries and turn mouse back on
3. Daemon detects Kindle is active (you just pressed a button)
4. Reconnects every **3 seconds** until mouse found
5. **Result**: Quick reconnection, typically within 10-15 seconds

### Scenario 2: Kindle is sitting idle
1. BLE mouse disconnects
2. Kindle screen is off, no buttons pressed
3. Daemon detects Kindle is idle
4. Reconnects every **30 seconds** to save battery
5. **Result**: Battery-friendly slow reconnection

### Scenario 3: Wake from idle
1. Kindle has been idle for 5 minutes, reconnecting every 30s
2. You press a button to wake the screen
3. Activity detected immediately
4. Next reconnection happens in **3 seconds** instead of 30
5. **Result**: Responsive to user interaction

## Battery Impact

**Before (exponential backoff)**:
- First attempt: 30s timeout
- Delays increase: 5s → 10s → 20s → 60s
- Problem: Slower when you actually need it

**After (activity-based)**:
- Connection timeout: 10s (saves 20s per attempt)
- Active delay: 3s (fast when needed)
- Idle delay: 30s (saves battery when not needed)
- Smart: Adapts to actual usage patterns

## Monitoring

View activity status in logs:
```bash
ssh kindle 'tail -f /var/log/ble_hid_daemon.log | grep -E "(active|idle)"'
```

You'll see messages like:
```
Kindle is active, reconnecting to 5C:2B:3E:50:4F:04/P in 3 seconds...
Kindle is idle, reconnecting to 5C:2B:3E:50:4F:04/P in 30 seconds...
```

## Technical Details

The activity monitor:
1. Opens all `/dev/input/event*` devices in non-blocking mode
2. Uses `select()` to efficiently wait for input events
3. Updates `last_activity_time` timestamp when events detected
4. Runs asynchronously in background task
5. Falls back gracefully if input devices can't be opened

## Author

Lucas Zampieri <lzampier@redhat.com>
December 2025
