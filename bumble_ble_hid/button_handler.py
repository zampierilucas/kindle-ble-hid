#!/usr/bin/env python3
"""
Button Handler

Processes HID reports, maps button presses using device-specific
mappers, and executes configured shell scripts.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

import json
import os
import subprocess
import time
from typing import Dict, Optional

from config import config
from logging_utils import log
from devices.base import ButtonMapper
from devices import get_mapper_for_device

__all__ = ['ButtonHandler']


class ButtonHandler:
    """Handles HID reports and executes button scripts.

    Responsibilities:
    - Parse HID reports to extract button data
    - Map raw button data to standardized codes (via ButtonMapper)
    - Apply debouncing to prevent duplicate executions
    - Execute shell scripts based on button mappings
    """

    def __init__(self, config_path: Optional[str] = None, mapper: Optional[ButtonMapper] = None):
        """Initialize button handler.

        Args:
            config_path: Path to button_config.json (uses default if None)
            mapper: Button mapper instance (auto-detected later if None)
        """
        self.config_path = config_path or config.button_config_file
        self.mapper = mapper  # Will be set when device connects
        self.button_scripts: Dict[str, str] = {}
        self.debounce_ms = config.debounce_ms
        self.log_button_presses = config.log_button_presses
        self.last_execution_time = 0.0

        self._load_config()

    def set_device(self, device_name: Optional[str]):
        """Set the button mapper based on connected device name.

        Args:
            device_name: BLE device name (e.g., "BLE-M3", "BEAUTY-R1")
        """
        self.mapper = get_mapper_for_device(device_name)
        log.info(f"Using button mapper: {self.mapper.device_name}")

    def _load_config(self):
        """Load button-to-script mappings from JSON config."""
        try:
            with open(self.config_path, 'r') as f:
                cfg = json.load(f)

            self.button_scripts = cfg.get('buttons', {})
            self.debounce_ms = cfg.get('debounce_ms', self.debounce_ms)
            self.log_button_presses = cfg.get('log_button_presses', self.log_button_presses)

            log.success(f"Loaded button configuration from {self.config_path}")
            log.info(f"Configured {len(self.button_scripts)} button mappings")

            for button_hex, script_path in self.button_scripts.items():
                log.detail(f"{button_hex} -> {script_path}")

        except FileNotFoundError:
            log.warning(f"Config file not found: {self.config_path}")
            log.warning("Using default empty configuration")

        except json.JSONDecodeError as e:
            log.error(f"Error parsing config file: {e}")
            log.warning("Using default empty configuration")

    def handle_report(self, report_data: bytes) -> bool:
        """Process an HID report and execute script if appropriate.

        Args:
            report_data: Raw HID report bytes

        Returns:
            True if a script was executed, False otherwise
        """
        # Need at least report_id and button_state
        if len(report_data) < 2:
            return False

        # Ensure we have a mapper (use default if not set)
        if self.mapper is None:
            self.set_device(None)

        # Extract fields from report
        button_state = report_data[1]
        x_movement = report_data[2] if len(report_data) > 2 else 0
        y_movement = report_data[3] if len(report_data) > 3 else 0

        # Ignore release events
        if self.mapper.is_release_event(button_state):
            return False

        # Map to standardized button code
        button_code, button_name = self.mapper.map(button_state, x_movement, y_movement)

        # Ignore unrecognized/noise patterns
        if button_code is None:
            return False

        # Apply debouncing
        if not self._debounce_check():
            return False

        # Log the button press with raw data
        if self.log_button_presses:
            log.info(f"Button press: {button_name} (raw: 0x{button_state:02x}, x:{x_movement:02x}, y:{y_movement:02x})")

        # Execute the script
        return self._execute_script(button_code, button_name)

    def _debounce_check(self) -> bool:
        """Check if enough time has passed since last execution.

        Returns:
            True if we should proceed, False if debouncing
        """
        current_time = time.time()
        debounce_sec = self.debounce_ms / 1000.0

        if current_time - self.last_execution_time < debounce_sec:
            return False

        self.last_execution_time = current_time
        return True

    def _execute_script(self, button_code: int, button_name: str) -> bool:
        """Execute the script mapped to a button code.

        Args:
            button_code: Standardized button code (0x01, 0x02, etc.)
            button_name: Human-readable button name for logging

        Returns:
            True if script was executed, False otherwise
        """
        button_hex = f"0x{button_code:02x}"
        script_path = self.button_scripts.get(button_hex)

        if not script_path:
            log.warning(f"No script configured for button {button_hex}")
            return False

        if not os.path.exists(script_path):
            log.error(f"Script not found: {script_path}")
            return False

        try:
            subprocess.Popen(
                [script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            log.success(f"Executed: {script_path}")
            return True

        except Exception as e:
            log.error(f"Failed to execute script: {e}")
            return False

    def execute_disconnect_script(self):
        """Execute the reading end script on disconnection."""
        script_path = config.reading_end_script

        if not os.path.exists(script_path):
            log.warning(f"Reading end script not found: {script_path}")
            return

        try:
            log.info(f"Executing reading end script: {script_path}")
            subprocess.Popen(
                [script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            log.success("Reading end script launched")

        except Exception as e:
            log.error(f"Failed to execute reading end script: {e}")
