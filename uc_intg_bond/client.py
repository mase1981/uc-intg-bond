"""
Bond API client for Unfolded Circle integration.

:copyright: (c) 2024 by Meir Miyara
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import ssl
from typing import Any, Dict, List, Optional

import aiohttp
import certifi

_LOG = logging.getLogger(__name__)


class BondClient:
    """Bond Local API client."""
    
    def __init__(self, config):
        """Initialize the Bond client."""
        self._config = config
        self._session: Optional[aiohttp.ClientSession] = None
        _LOG.info("Bond client initialized")

    async def unlock_with_pin(self, pin: str) -> bool:
        """Unlock Bond device using PIN."""
        try:
            if not self._config.get_bond_ip():
                _LOG.error("No Bond IP configured")
                return False

            url = f"http://{self._config.get_bond_ip()}/v2/token"
            data = {"locked": 0, "pin": pin}

            _LOG.debug("Attempting to unlock Bond device with PIN")
            session = await self._get_session()
            async with session.patch(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    _LOG.debug(f"Unlock response: {result}")
                    return True
                else:
                    _LOG.error(f"Failed to unlock Bond device: HTTP {response.status}")
                    return False

        except Exception as e:
            _LOG.error(f"Error unlocking Bond device: {e}")
            return False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with proper SSL context."""
        if self._session is None or self._session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'UC-Bond-Integration/1.0.0'}
            )
        return self._session
    
    def is_configured(self) -> bool:
        """Check if client is configured with valid connection details."""
        bond_ip = self._config.get_bond_ip()
        bond_token = self._config.get_bond_token()
        return bond_ip is not None and bond_token is not None
    
    async def discover_bonds(self) -> List[Dict[str, Any]]:
        """Discover Bond devices on the local network using mDNS."""
        try:
            from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
            
            bonds = []
            
            class BondListener(ServiceListener):
                def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    try:
                        info = zc.get_service_info(type_, name)
                        if info and info.addresses:
                            address = None
                            for addr in info.addresses:
                                if len(addr) == 4:  # IPv4
                                    address = ".".join(str(b) for b in addr)
                                    break
                            
                            if address:
                                bond_info = {
                                    "ip": address,
                                    "port": info.port,
                                    "name": name.replace("._bond._tcp.local.", ""),
                                }
                                
                                if info.properties:
                                    bond_info["properties"] = {
                                        k.decode(): v.decode() if v else ""
                                        for k, v in info.properties.items()
                                    }
                                
                                bonds.append(bond_info)
                                _LOG.info(f"Discovered Bond: {bond_info}")
                    except Exception as e:
                        _LOG.debug(f"Error processing discovered service: {e}")
                
                def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
                
                def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
            
            zeroconf = Zeroconf()
            listener = BondListener()
            browser = ServiceBrowser(zeroconf, "_bond._tcp.local.", listener)
            
            await asyncio.sleep(5)
            
            browser.cancel()
            zeroconf.close()
            
            _LOG.info(f"Discovered {len(bonds)} Bond device(s)")
            return bonds
            
        except ImportError:
            _LOG.warning("zeroconf not available, cannot discover Bond devices")
            return []
        except Exception as e:
            _LOG.error(f"Error during Bond discovery: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """Test connection to Bond device."""
        try:
            bond_ip = self._config.get_bond_ip()
            if not bond_ip:
                _LOG.error("No Bond IP configured")
                return False
            
            session = await self._get_session()
            url = f"http://{bond_ip}/v2/sys/version"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOG.info(f"Bond connection successful: {data.get('target', 'Unknown')} v{data.get('fw_ver', 'Unknown')}")
                    return True
                else:
                    _LOG.error(f"Bond connection failed: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            _LOG.error(f"Error testing Bond connection: {e}")
            return False
    
    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        """Get Bond device information."""
        try:
            data = await self._make_request("GET", "/v2/sys/version")
            if data:
                _LOG.debug(f"Bond device info: {data}")
                return data
            return None
        except Exception as e:
            _LOG.error(f"Error getting device info: {e}")
            return None
    
    async def get_token(self) -> Optional[Dict[str, Any]]:
        """Get Bond access token."""
        try:
            bond_ip = self._config.get_bond_ip()
            if not bond_ip:
                return None
            
            session = await self._get_session()
            url = f"http://{bond_ip}/v2/token"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOG.debug("Successfully obtained Bond token")
                    return data
                else:
                    _LOG.error(f"Failed to get Bond token: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            _LOG.error(f"Error getting Bond token: {e}")
            return None
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make an authenticated request to the Bond API."""
        try:
            bond_ip = self._config.get_bond_ip()
            bond_token = self._config.get_bond_token()
            
            if not bond_ip:
                _LOG.error("No Bond IP configured")
                return None
            
            session = await self._get_session()
            url = f"http://{bond_ip}{endpoint}"
            
            headers = kwargs.get("headers", {})
            if bond_token:
                headers["BOND-Token"] = bond_token
            kwargs["headers"] = headers
            
            async with session.request(method, url, **kwargs) as response:
                if 200 <= response.status < 300:
                    if response.status == 204:
                        return {}
                    return await response.json()
                
                _LOG.error(f"API request failed: {method} {url} - Status: {response.status}")
                return None
                
        except Exception as e:
            _LOG.error(f"Error making request: {e}")
            return None
    
    async def get_devices(self) -> Optional[Dict[str, Any]]:
        """Get list of devices from Bond."""
        return await self._make_request("GET", "/v2/devices")
    
    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get specific device information."""
        return await self._make_request("GET", f"/v2/devices/{device_id}")
    
    async def get_device_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device state."""
        return await self._make_request("GET", f"/v2/devices/{device_id}/state")
    
    async def execute_action(self, device_id: str, action: str, argument: Any = None) -> bool:
        """Execute an action on a device."""
        try:
            data = {}
            if argument is not None:
                data["argument"] = argument
            
            result = await self._make_request(
                "PUT", 
                f"/v2/devices/{device_id}/actions/{action}",
                json=data
            )
            return result is not None
        except Exception as e:
            _LOG.error(f"Error executing action {action} on device {device_id}: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()