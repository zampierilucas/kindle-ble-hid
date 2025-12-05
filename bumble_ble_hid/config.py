#!/usr/bin/env python3
"""
Centralized Configuration

All paths, timeouts, and settings in one place.
Reads from config.ini if present, otherwise uses defaults.

Author: Lucas Zampieri <lzampier@redhat.com>
"""

import configparser
import os
from typing import Optional

__all__ = ['config', 'Config']


class Config:
    """Singleton configuration manager"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self):
        """Load configuration from config.ini or use defaults"""
        # Base path - where the module is installed
        self.base_path = '/mnt/us/bumble_ble_hid'

        # Try to load config.ini
        config_file = os.path.join(self.base_path, 'config.ini')
        self._parser = configparser.ConfigParser()

        if os.path.exists(config_file):
            self._parser.read(config_file)

        # Paths
        self.cache_dir = self._get('paths', 'cache_dir',
                                   f'{self.base_path}/cache')
        self.pairing_keys_file = os.path.join(self.cache_dir, 'pairing_keys.json')
        self.button_config_file = self._get('paths', 'button_config',
                                            f'{self.base_path}/button_config.json')
        self.devices_config_file = self._get('paths', 'devices_config',
                                             f'{self.base_path}/devices.conf')
        self.scripts_dir = self._get('paths', 'scripts_dir',
                                     f'{self.base_path}/Scripts')
        self.reading_end_script = os.path.join(self.scripts_dir, 'readingEnd.sh')
        self.log_file = self._get('logging', 'log_file',
                                  '/var/log/ble_hid_daemon.log')

        # Transport
        self.transport = self._get('transport', 'hci_transport',
                                   'file:/dev/stpbt')

        # Connection timeouts (seconds)
        self.reconnect_delay = self._getint('connection', 'reconnect_delay', 5)
        self.cycle_timeout = self._getint('connection', 'cycle_timeout', 90)
        self.hci_reset_timeout = self._getint('connection', 'hci_reset_timeout', 10)
        self.connect_timeout = self._getint('connection', 'connect_timeout', 30)
        self.transport_timeout = self._getint('connection', 'transport_timeout', 30)

        # Button handling
        self.debounce_ms = self._getint('buttons', 'debounce_ms', 200)
        self.log_button_presses = self._getbool('buttons', 'log_button_presses', True)

        # Device identity
        self.device_name = self._get('device', 'name', 'Kindle-BLE-HID')
        self.device_address = self._get('device', 'address', 'F0:F0:F0:F0:F0:F0')

    def _get(self, section: str, key: str, default: str) -> str:
        """Get string value from config"""
        try:
            return self._parser.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def _getint(self, section: str, key: str, default: int) -> int:
        """Get integer value from config"""
        try:
            return self._parser.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default

    def _getbool(self, section: str, key: str, default: bool) -> bool:
        """Get boolean value from config"""
        try:
            return self._parser.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default

    def get_device_address(self) -> Optional[str]:
        """Load device address from devices.conf"""
        if not os.path.exists(self.devices_config_file):
            return None

        with open(self.devices_config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    return line

        return None


# Global singleton instance
config = Config()
