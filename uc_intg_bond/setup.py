"""
Setup handler for Bond integration.

:copyright: (c) 2024 by Meir Miyara
:license: MPL-2.0, see LICENSE for more details.
"""
import logging
from typing import Any, Callable, Coroutine

import ucapi

from uc_intg_bond.client import BondClient
from uc_intg_bond.config import BondConfig

_LOG = logging.getLogger(__name__)


class BondSetup:
    """Setup handler for Bond integration."""
    
    def __init__(self, config: BondConfig, client: BondClient, setup_complete_callback: Callable[[], Coroutine[Any, Any, None]]):
        self._config = config
        self._client = client
        self._setup_complete_callback = setup_complete_callback
    
    async def setup_handler(self, msg: ucapi.SetupDriver) -> ucapi.SetupAction:
        """Handle setup requests from Remote."""
        _LOG.info("Setup handler called with: %s", type(msg).__name__)
        
        if isinstance(msg, ucapi.DriverSetupRequest):
            return await self._handle_driver_setup_request(msg)
        elif isinstance(msg, ucapi.UserDataResponse):
            return await self._handle_user_data_response(msg)
        elif isinstance(msg, ucapi.UserConfirmationResponse):
            return await self._handle_user_confirmation_response(msg)
        elif isinstance(msg, ucapi.AbortDriverSetup):
            return await self._handle_abort_setup(msg)
        
        return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
    
    async def _handle_driver_setup_request(self, msg: ucapi.DriverSetupRequest) -> ucapi.SetupAction:
        """Handle initial setup request."""
        _LOG.debug("Handling driver setup request.")
        
        if self._config.is_configured() and not msg.reconfigure:
            _LOG.info("Already configured, checking if working...")
            
            if self._config.get_bond_token():
                _LOG.info("Token exists, proceeding to completion")
                await self._setup_complete_callback() 
                return ucapi.SetupComplete()
            else:
                _LOG.warning("Configuration exists but no token - need to get token")
        
        if msg.setup_data:
            bond_ip = msg.setup_data.get("bond_ip", "").strip()
            bond_pin = msg.setup_data.get("bond_pin", "").strip()
            
            if bond_ip:
                _LOG.info(f"Bond IP provided: {bond_ip}")
                if bond_pin:
                    _LOG.info(f"Bond PIN provided: {'*' * len(bond_pin)}")
                return await self._test_bond_connection(bond_ip, bond_pin, "Bond Device")
            else:
                _LOG.error("No Bond IP provided in setup data")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
        _LOG.warning("No setup data provided")
        return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
    
    async def _test_bond_connection(self, bond_ip: str, bond_pin: str, bond_name: str) -> ucapi.SetupAction:
        """Test connection to a specific Bond device."""
        _LOG.info(f"Testing connection to Bond at {bond_ip}")
        
        try:
            self._config.set_bond_ip(bond_ip)
            
            if not await self._client.test_connection():
                _LOG.error("Failed to connect to Bond device")
                return ucapi.SetupError(ucapi.IntegrationSetupError.CONNECTION_REFUSED)
            
            device_info = await self._client.get_device_info()
            if not device_info:
                _LOG.error("Failed to get Bond device information")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
            
            token_info = await self._client.get_token()
            if not token_info:
                _LOG.error("Failed to get Bond token info")
                return ucapi.SetupError(ucapi.IntegrationSetupError.AUTHORIZATION_ERROR)
            
            if token_info.get("locked") == 1:
                _LOG.warning("Bond device is locked - attempting to unlock with PIN")
                
                if not bond_pin:
                    _LOG.error("Bond device is locked but no PIN provided")
                    return ucapi.RequestUserConfirmation(
                        title={"en": "Bond Device Locked"},
                        header={"en": "The Bond device is locked and requires authentication."},
                        footer={"en": "Please power cycle your Bond device (unplug and plug back in) and try setup again within 10 minutes."}
                    )
                
                if await self._client.unlock_with_pin(bond_pin):
                    _LOG.info("Successfully unlocked Bond device with PIN")
                    token_info = await self._client.get_token()
                    if not token_info:
                        _LOG.error("Failed to get token after unlock")
                        return ucapi.SetupError(ucapi.IntegrationSetupError.AUTHORIZATION_ERROR)
                else:
                    _LOG.error("Failed to unlock Bond device with provided PIN")
                    return ucapi.SetupError(ucapi.IntegrationSetupError.AUTHORIZATION_ERROR)
            
            token = token_info.get("token")
            if not token:
                _LOG.error("No token in response after unlock")
                return ucapi.SetupError(ucapi.IntegrationSetupError.AUTHORIZATION_ERROR)
            
            self._config.set_bond_token(token)
            _LOG.info("Token saved successfully")
            
            return await self._discover_and_complete_setup(device_info, bond_name)
            
        except Exception as e:
            _LOG.error("Error testing Bond connection: %s", e, exc_info=True)
            return ucapi.SetupError(ucapi.IntegrationSetupError.CONNECTION_REFUSED)
    
    async def _discover_and_complete_setup(self, device_info: dict, bond_name: str) -> ucapi.SetupAction:
        """Discover devices and complete setup."""
        try:
            devices_data = await self._client.get_devices()
            if devices_data:
                device_count = len([k for k in devices_data.keys() if not k.startswith('_')])
                _LOG.info(f"Discovered {device_count} Bond devices")
                
                discovered_devices = {}
                for device_id, device_hash in devices_data.items():
                    if device_id.startswith("_"):
                        continue
                    
                    try:
                        device_info_detail = await self._client.get_device(device_id)
                        if device_info_detail:
                            discovered_devices[device_id] = {
                                "name": device_info_detail.get("name", f"Device {device_id}"),
                                "type": device_info_detail.get("type", "Unknown"),
                                "actions": device_info_detail.get("actions", []),
                                "location": device_info_detail.get("location", "")
                            }
                            _LOG.info(f"Device: {device_info_detail.get('name')} ({device_info_detail.get('type')}) - {len(device_info_detail.get('actions', []))} actions")
                    except Exception as e:
                        _LOG.warning(f"Failed to get info for device {device_id}: {e}")
                
                self._config.set_devices(discovered_devices)
                _LOG.info(f"Saved {len(discovered_devices)} devices to configuration")
            else:
                _LOG.warning("No devices discovered on Bond hub")
            
            self._config.set_bond_name(device_info.get("make", bond_name))
            
            _LOG.info("Successfully connected to Bond device and discovered devices")
            await self._setup_complete_callback()
            return ucapi.SetupComplete()
            
        except Exception as e:
            _LOG.error("Error during device discovery: %s", e, exc_info=True)
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
    
    async def _handle_user_data_response(self, msg: ucapi.UserDataResponse) -> ucapi.SetupAction:
        """Handle user input responses."""
        _LOG.debug("Handling user data response: %s", msg.input_values)
        
        bond_ip = msg.input_values.get("bond_ip", "").strip()
        bond_pin = msg.input_values.get("bond_pin", "").strip()
        
        if bond_ip:
            return await self._test_bond_connection(bond_ip, bond_pin, "Bond Device")
        else:
            _LOG.error("No IP address provided")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
    
    async def _handle_user_confirmation_response(self, msg: ucapi.UserConfirmationResponse) -> ucapi.SetupAction:
        """Handle user confirmation responses."""
        _LOG.debug("Handling user confirmation response: %s", msg.confirm)
        
        if msg.confirm:
            _LOG.info("User confirmed power cycle, retrying setup")
            bond_ip = self._config.get_bond_ip()
            if bond_ip:
                return await self._test_bond_connection(bond_ip, "", "Bond Device")
            else:
                _LOG.error("No Bond IP in config for retry")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        else:
            _LOG.info("User cancelled power cycle confirmation")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
    
    async def _handle_abort_setup(self, msg: ucapi.AbortDriverSetup) -> ucapi.SetupAction:
        """Handle setup abortion."""
        _LOG.info("Setup aborted: %s", msg.error)
        self._config.clear_config()
        return ucapi.SetupError(msg.error)