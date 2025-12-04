#!/usr/bin/env python3
"""
Kindle Power and Idle State Monitoring

Provides unified suspend/resume detection and idle state monitoring for Kindle devices.
Supports both Kindle-specific LIPC interfaces and standard Linux /sys/power interfaces.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

import os
import select
import time
import subprocess
import logging
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device power states"""
    ACTIVE = "active"           # User actively interacting
    IDLE = "idle"               # No input but device awake
    DEEP_IDLE = "deep_idle"     # Idle for extended period
    RESUMED = "resumed"         # Just resumed from suspend
    SUSPENDED = "suspended"     # Device suspended (only detectable after resume)


@dataclass
class SuspendEvent:
    """Information about a suspend/resume cycle"""
    resume_time: float
    suspend_duration: float  # seconds
    suspend_count: int


class SuspendMonitor:
    """
    Monitor system suspend/resume cycles using kernel interfaces.

    Primary method: /sys/power/suspend_stats/success
    Fallback method: /proc/uptime discontinuity detection
    """

    def __init__(self):
        self.last_suspend_count = self._read_suspend_count()
        self.last_uptime = self._read_uptime()
        self.last_check_time = time.time()
        self.supports_suspend_stats = os.path.exists('/sys/power/suspend_stats/success')

        if not self.supports_suspend_stats:
            logger.warning("Suspend stats not available, using uptime discontinuity detection")

    def _read_suspend_count(self) -> int:
        """Read successful suspend count from kernel"""
        try:
            with open('/sys/power/suspend_stats/success', 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError, PermissionError):
            return 0

    def _read_uptime(self) -> float:
        """Read system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.read().split()[0])
        except (FileNotFoundError, ValueError):
            return 0.0

    def _read_last_hw_sleep(self) -> float:
        """Read duration of last hardware sleep in seconds"""
        try:
            with open('/sys/power/suspend_stats/last_hw_sleep', 'r') as f:
                microseconds = int(f.read().strip())
                return microseconds / 1_000_000
        except (FileNotFoundError, ValueError, PermissionError):
            return 0.0

    def check_suspend_resume(self) -> Tuple[bool, Optional[SuspendEvent]]:
        """
        Check if system has resumed from suspend since last check.

        Returns:
            (resumed, event): True if resumed, with SuspendEvent details if available
        """
        current_time = time.time()
        current_uptime = self._read_uptime()

        if self.supports_suspend_stats:
            # Primary method: Check suspend stats
            current_count = self._read_suspend_count()

            if current_count > self.last_suspend_count:
                sleep_duration = self._read_last_hw_sleep()
                event = SuspendEvent(
                    resume_time=current_time,
                    suspend_duration=sleep_duration,
                    suspend_count=current_count
                )

                self.last_suspend_count = current_count
                self.last_uptime = current_uptime
                self.last_check_time = current_time

                logger.info(f"Resume detected! Slept for {sleep_duration:.1f}s")
                return True, event
        else:
            # Fallback method: Detect uptime discontinuity
            real_elapsed = current_time - self.last_check_time
            uptime_elapsed = current_uptime - self.last_uptime

            # If real time is significantly more than uptime, system was suspended
            discontinuity = real_elapsed - uptime_elapsed

            if discontinuity > 2.0:  # 2 second threshold to avoid false positives
                event = SuspendEvent(
                    resume_time=current_time,
                    suspend_duration=discontinuity,
                    suspend_count=0  # Unknown without suspend_stats
                )

                logger.info(f"Resume detected via uptime! Slept for ~{discontinuity:.1f}s")
                self.last_uptime = current_uptime
                self.last_check_time = current_time
                return True, event

        self.last_uptime = current_uptime
        self.last_check_time = current_time
        return False, None


class LIPCMonitor:
    """
    Monitor Kindle-specific power events using LIPC (Lab126 IPC).

    Only available on actual Kindle devices with LIPC daemon running.
    """

    def __init__(self):
        self.available = self._check_lipc_available()
        if not self.available:
            logger.info("LIPC not available (not running on Kindle)")

    def _check_lipc_available(self) -> bool:
        """Check if lipc-get-prop command is available"""
        try:
            result = subprocess.run(
                ['which', 'lipc-get-prop'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_power_state(self) -> Optional[str]:
        """
        Query current power state from powerd.

        Returns: 'active', 'screenSaver', 'readyToSuspend', 'suspended', or None
        """
        if not self.available:
            return None

        try:
            result = subprocess.run(
                ['lipc-get-prop', 'com.lab126.powerd', 'state'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def is_charging(self) -> Optional[bool]:
        """Check if device is charging"""
        if not self.available:
            return None

        try:
            result = subprocess.run(
                ['lipc-get-prop', 'com.lab126.powerd', 'isCharging'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip() == '1'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def get_battery_level(self) -> Optional[int]:
        """Get battery level percentage"""
        if not self.available:
            return None

        try:
            result = subprocess.run(
                ['lipc-get-prop', 'com.lab126.powerd', 'battLevel'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

        return None

    def prevent_screensaver(self, prevent: bool):
        """Prevent or allow screensaver activation"""
        if not self.available:
            return

        try:
            subprocess.run(
                ['lipc-set-prop', 'com.lab126.powerd', 'preventScreenSaver', '1' if prevent else '0'],
                capture_output=True,
                timeout=2
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def defer_suspend(self, defer: bool):
        """Defer or allow system suspend"""
        if not self.available:
            return

        try:
            subprocess.run(
                ['lipc-set-prop', 'com.lab126.powerd', 'deferSuspend', '1' if defer else '0'],
                capture_output=True,
                timeout=2
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


class KindlePowerMonitor:
    """
    Unified power and idle state monitoring for Kindle devices.

    Combines:
    - Suspend/resume detection (SuspendMonitor)
    - LIPC power events (LIPCMonitor, if available)
    - Input activity monitoring (via external activity monitor)

    Usage:
        monitor = KindlePowerMonitor()
        monitor.set_activity_checker(your_activity_function)

        state = monitor.get_device_state()
        if state == DeviceState.RESUMED:
            # Reinitialize connections
            pass
    """

    def __init__(self, idle_threshold: float = 60.0, deep_idle_threshold: float = 300.0):
        """
        Initialize power monitor.

        Args:
            idle_threshold: Seconds of no input before considering idle (default: 60s)
            deep_idle_threshold: Seconds of no input for deep idle (default: 300s)
        """
        self.suspend_monitor = SuspendMonitor()
        self.lipc_monitor = LIPCMonitor()
        self.idle_threshold = idle_threshold
        self.deep_idle_threshold = deep_idle_threshold

        # External activity checker (set via set_activity_checker)
        self._activity_checker: Optional[Callable[[], Tuple[bool, float]]] = None

        # Track last resume event
        self.last_resume_event: Optional[SuspendEvent] = None
        self.resume_handled = True

    def set_activity_checker(self, checker: Callable[[], Tuple[bool, float]]):
        """
        Set external activity checker function.

        Args:
            checker: Function that returns (has_activity: bool, idle_seconds: float)
        """
        self._activity_checker = checker

    def get_device_state(self) -> DeviceState:
        """
        Get current device state.

        Returns:
            DeviceState enum value
        """
        # Check for suspend/resume first
        resumed, event = self.suspend_monitor.check_suspend_resume()
        if resumed:
            self.last_resume_event = event
            self.resume_handled = False
            return DeviceState.RESUMED

        # If we have unhandled resume, keep returning RESUMED until cleared
        if not self.resume_handled:
            return DeviceState.RESUMED

        # Check activity level
        if self._activity_checker:
            has_activity, idle_seconds = self._activity_checker()

            if has_activity:
                return DeviceState.ACTIVE
            elif idle_seconds < self.idle_threshold:
                return DeviceState.ACTIVE
            elif idle_seconds < self.deep_idle_threshold:
                return DeviceState.IDLE
            else:
                return DeviceState.DEEP_IDLE

        # No activity checker, can only detect resume
        return DeviceState.ACTIVE

    def mark_resume_handled(self):
        """Mark that the resume event has been handled"""
        self.resume_handled = True

    def get_lipc_state(self) -> Optional[str]:
        """Get LIPC power state if available"""
        return self.lipc_monitor.get_power_state()

    def get_battery_info(self) -> dict:
        """Get battery information"""
        return {
            'level': self.lipc_monitor.get_battery_level(),
            'charging': self.lipc_monitor.is_charging()
        }

    def prevent_sleep(self, prevent: bool):
        """Prevent device from sleeping (LIPC only)"""
        self.lipc_monitor.prevent_screensaver(prevent)
        self.lipc_monitor.defer_suspend(prevent)


# Example integration with activity monitoring
def example_integration():
    """
    Example of how to integrate with ble_hid_daemon.py
    """
    # Initialize power monitor
    power_monitor = KindlePowerMonitor(
        idle_threshold=60.0,      # 60s idle
        deep_idle_threshold=300.0  # 5m deep idle
    )

    # Mock activity monitoring (replace with actual implementation)
    last_activity_time = time.time()
    input_fds = []  # Your actual input file descriptors

    def check_activity():
        """Check for input activity"""
        nonlocal last_activity_time

        if not input_fds:
            return False, time.time() - last_activity_time

        # Non-blocking check for input
        readable, _, _ = select.select(input_fds, [], [], 0)
        if readable:
            last_activity_time = time.time()
            return True, 0.0

        idle_seconds = time.time() - last_activity_time
        return False, idle_seconds

    # Register activity checker
    power_monitor.set_activity_checker(check_activity)

    # Main loop
    while True:
        state = power_monitor.get_device_state()

        if state == DeviceState.RESUMED:
            print("Device resumed from suspend!")
            event = power_monitor.last_resume_event
            if event:
                print(f"  Slept for: {event.suspend_duration:.1f}s")

            # Reinitialize BLE connections here
            # ...

            # Mark resume as handled
            power_monitor.mark_resume_handled()

        elif state == DeviceState.ACTIVE:
            print("Device active, reconnect quickly")
            # Use fast reconnect interval

        elif state == DeviceState.IDLE:
            print("Device idle, reduce reconnect frequency")
            # Use slower reconnect interval

        elif state == DeviceState.DEEP_IDLE:
            print("Device deep idle, minimal reconnects")
            # Use very slow reconnect interval or pause

        time.sleep(2)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Kindle Power Monitor - Test Mode")
    print("=" * 50)

    monitor = KindlePowerMonitor()

    print(f"Suspend stats available: {monitor.suspend_monitor.supports_suspend_stats}")
    print(f"LIPC available: {monitor.lipc_monitor.available}")

    if monitor.lipc_monitor.available:
        print(f"Power state: {monitor.get_lipc_state()}")
        battery = monitor.get_battery_info()
        print(f"Battery: {battery['level']}% (charging: {battery['charging']})")

    print("\nMonitoring for suspend/resume events (Ctrl+C to exit)...")
    print("Try suspending the device to test detection\n")

    try:
        while True:
            state = monitor.get_device_state()

            if state == DeviceState.RESUMED:
                event = monitor.last_resume_event
                print(f"\nRESUME DETECTED at {time.strftime('%H:%M:%S')}")
                if event:
                    print(f"  Suspend duration: {event.suspend_duration:.1f}s")
                    print(f"  Suspend count: {event.suspend_count}")
                monitor.mark_resume_handled()

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")
