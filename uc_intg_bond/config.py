"""
Configuration management for Bond integration.

:copyright: (c) 2024 by Meir Miyara
:license: MPL-2.0, see LICENSE for more details.
"""

import json
import logging
from typing import Any, Dict, Optional

_LOG = logging.getLogger(__name__)


class BondConfig:
    """Configuration management for Bond integration."""
    
    def __init__(self, config_file_path: str):
        """Initialize configuration with file path."""
        self._config_file_path = config_file_path
        self._config_data: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            with open(self._config_file_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
            _LOG.debug("Configuration loaded successfully")
        except FileNotFoundError:
            _LOG.debug("Configuration file not found, starting with empty config")
            self._config_data = {}
        except json.JSONDecodeError as e:
            _LOG.error("Error parsing configuration file: %s", e)
            self._config_data = {}
        except Exception as e:
            _LOG.error("Error loading configuration: %s", e)
            self._config_data = {}
    
    def _save_config(self) -> bool:
        """Save configuration to file."""
        try:
            with open(self._config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
            _LOG.debug("Configuration saved successfully")
            return True
        except Exception as e:
            _LOG.error("Error saving configuration: %s", e)
            return False
    
    def is_configured(self) -> bool:
        """Check if the integration is configured with valid Bond IP."""
        bond_ip = self.get_bond_ip()
        return bond_ip is not None and bond_ip.strip() != ""
    
    def set_bond_ip(self, bond_ip: str) -> bool:
        """Set Bond device IP address."""
        try:
            self._config_data["bond_ip"] = bond_ip.strip()
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting Bond IP: %s", e)
            return False
    
    def get_bond_ip(self) -> Optional[str]:
        """Get the Bond device IP address."""
        return self._config_data.get("bond_ip")
    
    def set_bond_token(self, token: str) -> bool:
        """Set Bond device local token."""
        try:
            self._config_data["bond_token"] = token
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting Bond token: %s", e)
            return False
    
    def get_bond_token(self) -> Optional[str]:
        """Get the Bond device local token."""
        return self._config_data.get("bond_token")
    
    def set_bond_info(self, bond_info: Dict[str, Any]) -> bool:
        """Set Bond device information."""
        try:
            self._config_data["bond_info"] = bond_info
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting Bond info: %s", e)
            return False
    
    def get_bond_info(self) -> Optional[Dict[str, Any]]:
        """Get stored Bond device information."""
        return self._config_data.get("bond_info")
    
    def get_polling_interval(self) -> int:
        """Get the polling interval in seconds."""
        return self._config_data.get("polling_interval", 30)
    
    def set_polling_interval(self, interval: int) -> bool:
        """Set the polling interval."""
        try:
            self._config_data["polling_interval"] = max(10, min(300, interval))
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting polling interval: %s", e)
            return False
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration data (for debugging)."""
        safe_config = self._config_data.copy()
        if "bond_token" in safe_config:
            safe_config["bond_token"] = "***HIDDEN***"
        return safe_config
    
    def reset_config(self) -> bool:
        """Reset all configuration data."""
        try:
            self._config_data = {}
            return self._save_config()
        except Exception as e:
            _LOG.error("Error resetting configuration: %s", e)
            return False
    
    def clear_config(self) -> bool:
        """Clear all configuration data."""
        return self.reset_config()
    
    def set_bond_name(self, name: str) -> bool:
        """Set Bond device name."""
        try:
            self._config_data["bond_name"] = name
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting Bond name: %s", e)
            return False
    
    def get_bond_name(self) -> Optional[str]:
        """Get the Bond device name."""
        return self._config_data.get("bond_name")
    
    def set_devices(self, devices: Dict[str, Any]) -> bool:
        """Set discovered Bond devices."""
        try:
            self._config_data["devices"] = devices
            return self._save_config()
        except Exception as e:
            _LOG.error("Error setting devices: %s", e)
            return False
    
    def get_devices(self) -> Dict[str, Any]:
        """Get discovered Bond devices."""
        return self._config_data.get("devices", {})