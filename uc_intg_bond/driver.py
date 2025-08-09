#!/usr/bin/env python3
"""
Bond integration driver for Unfolded Circle Remote.

:copyright: (c) 2024 by Meir Miyara
:license: MPL-2.0, see LICENSE for more details.
"""
import asyncio
import logging
import os
import signal
from typing import Optional

import ucapi

from uc_intg_bond.client import BondClient
from uc_intg_bond.config import BondConfig
from uc_intg_bond.remote import BondRemote
from uc_intg_bond.setup import BondSetup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

_LOG = logging.getLogger(__name__)

# Global State
loop = asyncio.get_event_loop()
api: Optional[ucapi.IntegrationAPI] = None
bond_client: Optional[BondClient] = None
bond_config: Optional[BondConfig] = None
remote: Optional[BondRemote] = None

async def on_setup_complete():
    """Callback executed when driver setup is complete."""
    global remote, bond_client, api
    _LOG.info("Setup complete. Creating entities...")

    if not api or not bond_client:
        _LOG.error("Cannot create entities: API or client not initialized.")
        await api.set_device_state(ucapi.DeviceStates.ERROR)
        return

    try:
        if not bond_client.is_configured():
            _LOG.error("Bond client is not configured after setup")
            await api.set_device_state(ucapi.DeviceStates.ERROR)
            return

        if not await bond_client.test_connection():
            _LOG.error("Bond connection test failed after setup")
            await api.set_device_state(ucapi.DeviceStates.ERROR)
            return

        discovered_devices = bond_client._config.get_devices()
        _LOG.info(f"Creating entities for {len(discovered_devices)} discovered devices")
        
        for device_id, device_info in discovered_devices.items():
            _LOG.debug(f"Device {device_id}: {device_info.get('name')} ({device_info.get('type')}) - {len(device_info.get('actions', []))} actions")

        remote = BondRemote(api, bond_client)
        api.available_entities.add(remote.entity)
        _LOG.info(f"Added remote entity: {remote.entity.id}")
        
        _LOG.info("Remote entity created successfully. Setting state to CONNECTED.")
        await api.set_device_state(ucapi.DeviceStates.CONNECTED)
        
    except Exception as e:
        _LOG.error(f"Error creating entities: {e}", exc_info=True)
        await api.set_device_state(ucapi.DeviceStates.ERROR)

async def on_r2_connect():
    """Handle Remote connection."""
    _LOG.info("Remote connected.")
    
    if api and bond_config and bond_config.is_configured():
        if not bond_client.is_configured():
            _LOG.info("Reinitializing Bond client from saved config...")
            
        if bond_client and await bond_client.test_connection():
            _LOG.info("Bond connection verified. Setting state to CONNECTED.")
            await api.set_device_state(ucapi.DeviceStates.CONNECTED)
        else:
            _LOG.warning("Bond connection failed. Setting state to ERROR.")
            await api.set_device_state(ucapi.DeviceStates.ERROR)
    else:
        _LOG.info("Integration not configured yet.")

async def on_disconnect():
    """Handle Remote disconnection."""
    _LOG.info("Remote disconnected.")

async def on_subscribe_entities(entity_ids: list[str]):
    """Handle entity subscription from Remote."""
    _LOG.info(f"Remote subscribed to entities: {entity_ids}")
    
    if remote and bond_client and bond_client.is_configured():
        _LOG.info("Ensuring remote entity has configured Bond client...")
        
        connection_ok = await bond_client.test_connection()
        _LOG.info(f"Bond client connection test: {'OK' if connection_ok else 'FAILED'}")
        
        if not connection_ok:
            _LOG.error("Bond client connection failed during entity subscription")
            await api.set_device_state(ucapi.DeviceStates.ERROR)
    
    if remote and remote.entity.id in entity_ids:
        _LOG.info("Remote entity subscribed - ready for commands")

async def on_unsubscribe_entities(entity_ids: list[str]):
    """Handle entity unsubscription from Remote."""
    _LOG.info(f"Remote unsubscribed from entities: {entity_ids}")

async def init_integration():
    """Initialize the integration objects and API."""
    global api, bond_client, bond_config
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    driver_json_path = os.path.join(project_root, "driver.json")
    
    if not os.path.exists(driver_json_path):
        driver_json_path = "driver.json"
        if not os.path.exists(driver_json_path):
            _LOG.error(f"Cannot find driver.json at {driver_json_path}")
            raise FileNotFoundError("driver.json not found")
    
    _LOG.info(f"Using driver.json from: {driver_json_path}")

    api = ucapi.IntegrationAPI(loop)

    config_path = os.path.join(api.config_dir_path, "config.json")
    _LOG.info(f"Using config file: {config_path}")
    bond_config = BondConfig(config_path)
    
    bond_client = BondClient(bond_config)

    setup_handler = BondSetup(bond_config, bond_client, on_setup_complete)
    
    await api.init(driver_json_path, setup_handler.setup_handler)
    
    api.add_listener(ucapi.Events.CONNECT, on_r2_connect)
    api.add_listener(ucapi.Events.DISCONNECT, on_disconnect)
    api.add_listener(ucapi.Events.SUBSCRIBE_ENTITIES, on_subscribe_entities)
    api.add_listener(ucapi.Events.UNSUBSCRIBE_ENTITIES, on_unsubscribe_entities)
    
    _LOG.info("Integration API initialized successfully")
    
async def main():
    """Main entry point."""
    _LOG.info("Starting Bond Integration Driver")
    
    try:
        await init_integration()
        
        if bond_config and bond_config.is_configured():
            _LOG.info("Integration is already configured")
            
            if await bond_client.test_connection():
                _LOG.info("Bond connection successful")
                
                discovered_devices = bond_config.get_devices()
                if discovered_devices:
                    _LOG.info(f"Found {len(discovered_devices)} configured devices")
                    await on_setup_complete()
                else:
                    _LOG.warning("No devices found in configuration")
                    await api.set_device_state(ucapi.DeviceStates.ERROR)
            else:
                _LOG.error("Cannot connect to configured Bond device")
                await api.set_device_state(ucapi.DeviceStates.ERROR)
        else:
            _LOG.warning("Integration is not configured. Waiting for setup...")
            await api.set_device_state(ucapi.DeviceStates.ERROR)

        _LOG.info("Integration is running. Press Ctrl+C to stop.")
        
    except Exception as e:
        _LOG.error(f"Failed to start integration: {e}", exc_info=True)
        if api:
            await api.set_device_state(ucapi.DeviceStates.ERROR)
        raise
    
def shutdown_handler(signum, frame):
    """Handle termination signals for graceful shutdown."""
    _LOG.warning(f"Received signal {signum}. Shutting down...")
    
    async def cleanup():
        try:
            if bond_client:
                _LOG.info("Closing Bond client...")
                await bond_client.close()
            
            _LOG.info("Cancelling remaining tasks...")
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            [task.cancel() for task in tasks]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            _LOG.error(f"Error during cleanup: {e}")
        finally:
            _LOG.info("Stopping event loop...")
            loop.stop()

    loop.create_task(cleanup())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        loop.run_until_complete(main())
        loop.run_forever()
    except (KeyboardInterrupt, asyncio.CancelledError):
        _LOG.info("Driver stopped.")
    except Exception as e:
        _LOG.error(f"Driver failed: {e}", exc_info=True)
    finally:
        if loop and not loop.is_closed():
            _LOG.info("Closing event loop...")
            loop.close()