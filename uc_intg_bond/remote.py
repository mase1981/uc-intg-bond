"""
Bond remote entity for Unfolded Circle integration.

:copyright: (c) 2024 by Meir Miyara
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

import ucapi
from ucapi.remote import Commands, Features, States
from ucapi.ui import Buttons, Size, create_btn_mapping, create_ui_icon, create_ui_text, UiPage

from uc_intg_bond.client import BondClient

_LOG = logging.getLogger(__name__)


class BondRemote:
    """Bond remote entity with clean device-per-page organization."""
    
    def __init__(self, api: ucapi.IntegrationAPI, client: BondClient):
        """Initialize Bond remote."""
        self._api = api
        self._client = client
        self._device_throttle = {}  # Track last command time per device
        self._global_throttle = 0  # Global throttle for all commands
        
        # Get discovered devices from config
        self._discovered_devices = self._client._config.get_devices()
        _LOG.info(f"Creating remote with {len(self._discovered_devices)} discovered devices")
        
        features = [Features.ON_OFF, Features.SEND_CMD]
        
        # Generate dynamic content based on discovered devices
        simple_commands = self._generate_simple_commands()
        button_mapping = self._generate_button_mapping()
        ui_pages = self._create_ui_pages()
        
        self.entity = ucapi.Remote(
            identifier="bond_remote_main",
            name={"en": "Bond Remote"},
            features=features,
            attributes={"state": States.ON},
            simple_commands=simple_commands,
            button_mapping=button_mapping,
            ui_pages=ui_pages,
            cmd_handler=self.cmd_handler
        )
        
        _LOG.info(f"Bond remote entity created with {len(simple_commands)} commands and {len(ui_pages)} UI pages")
    
    def _generate_simple_commands(self) -> List[str]:
        """Generate simple commands based on discovered devices."""
        commands = []
        
        if not self._discovered_devices:
            return ["NO_DEVICES"]
        
        # Device-specific commands
        for device_id, device_info in self._discovered_devices.items():
            device_name = device_info.get("name", f"Device_{device_id}")
            device_actions = device_info.get("actions", [])
            
            # Clean device name for command generation
            clean_name = self._clean_command_name(device_name)
            
            # Create commands for each device action
            for action in device_actions:
                cmd = f"{clean_name}_{action}".upper()
                commands.append(cmd)
        
        # Global commands if multiple devices
        if len(self._discovered_devices) > 1:
            commands.extend(["ALL_ON", "ALL_OFF", "ALL_TOGGLE"])
        
        return sorted(list(set(commands)))  # Remove duplicates and sort
    
    def _clean_command_name(self, name: str) -> str:
        """Clean a name for use in command generation."""
        # Remove special characters and spaces, keep only alphanumeric and underscores
        cleaned = "".join(c if c.isalnum() else "_" for c in name.upper())
        # Remove multiple consecutive underscores
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        # Remove leading/trailing underscores
        return cleaned.strip("_")
    
    def _generate_button_mapping(self) -> List[dict]:
        """Generate physical button mappings based on devices."""
        mappings = []
        
        if not self._discovered_devices:
            return mappings
        
        # Find primary device for power button
        primary_device = self._find_primary_device()
        if primary_device:
            device_name = self._clean_command_name(primary_device.get("name", "Device"))
            actions = primary_device.get("actions", [])
            
            # Power button mapping
            if "TogglePower" in actions:
                cmd = f"{device_name}_TOGGLEPOWER"
                mappings.append(create_btn_mapping(Buttons.POWER, cmd))
            elif "TurnOn" in actions:
                cmd = f"{device_name}_TURNON"
                mappings.append(create_btn_mapping(Buttons.POWER, cmd))
        
        # Volume buttons for speed/level control
        speed_device = self._find_device_with_actions(["IncreaseSpeed", "DecreaseSpeed"])
        if speed_device:
            device_name = self._clean_command_name(speed_device.get("name", "Device"))
            if "IncreaseSpeed" in speed_device.get("actions", []):
                mappings.append(create_btn_mapping(Buttons.VOLUME_UP, f"{device_name}_INCREASESPEED"))
            if "DecreaseSpeed" in speed_device.get("actions", []):
                mappings.append(create_btn_mapping(Buttons.VOLUME_DOWN, f"{device_name}_DECREASESPEED"))
        
        return mappings
    
    def _find_primary_device(self) -> Dict[str, Any]:
        """Find the primary device for main controls."""
        # Priority: Ceiling Fan > Fireplace > Light > Others
        priority_types = ["CF", "FP", "LT", "MS", "GX", "BD"]
        
        for device_type in priority_types:
            for device_info in self._discovered_devices.values():
                if device_info.get("type") == device_type:
                    return device_info
        
        # Return first device if no priority match
        return next(iter(self._discovered_devices.values())) if self._discovered_devices else {}
    
    def _find_device_with_actions(self, target_actions: List[str]) -> Dict[str, Any]:
        """Find a device that has any of the specified actions."""
        for device_info in self._discovered_devices.values():
            device_actions = device_info.get("actions", [])
            if any(action in device_actions for action in target_actions):
                return device_info
        return {}
    
    def _create_ui_pages(self) -> List[UiPage]:
        """Create UI pages - one main overview + one page per device."""
        pages = []
        
        if not self._discovered_devices:
            # Fallback page if no devices discovered
            main_page = UiPage(page_id="main", name="No Devices", grid=Size(4, 6))
            main_page.add(create_ui_text("No devices found", 0, 0, Size(4, 1)))
            pages.append(main_page)
            return pages
        
        # Main overview page
        main_page = self._create_main_overview_page()
        pages.append(main_page)
        
        # One page per device with device name as header
        for device_id, device_info in self._discovered_devices.items():
            device_page = self._create_device_page(device_id, device_info)
            if device_page:
                pages.append(device_page)
        
        return pages
    
    def _create_main_overview_page(self) -> UiPage:
        """Create the main overview page with device names above status buttons."""
        main_page = UiPage(page_id="main", name="Bond Devices", grid=Size(4, 6))
        
        # Add header
        main_page.add(create_ui_text("Bond Hub Connected", 0, 0, Size(4, 1)))
        
        x, y = 0, 1  # Start after header
        device_count = 0
        
        for device_id, device_info in self._discovered_devices.items():
            if y >= 4:  # Leave room for global controls
                break
                
            device_name = device_info.get("name", f"Device {device_id}")
            actions = device_info.get("actions", [])
            
            # Choose primary action
            primary_action = self._get_primary_action(actions)
            
            if primary_action:
                clean_name = self._clean_command_name(device_name)
                cmd = f"{clean_name}_{primary_action}".upper()
                
                # Add device name above (truncate if too long)
                display_name = device_name[:10] if len(device_name) > 10 else device_name
                main_page.add(create_ui_text(display_name, x, y, Size(2, 1)))
                
                # Add status button below with ON/OFF text
                status_text = self._get_device_status_text(device_id, primary_action)
                main_page.add(create_ui_text(status_text, x, y + 1, Size(2, 1), cmd))
                
                x += 2
                if x >= 4:
                    x = 0
                    y += 3  # Move down to next row pair
                
                device_count += 1
        
        # Add global controls at bottom if we have multiple devices
        if len(self._discovered_devices) > 1:
            if y < 5:
                main_page.add(create_ui_text("All On", 0, 5, Size(2, 1), "ALL_ON"))
                main_page.add(create_ui_text("All Off", 2, 5, Size(2, 1), "ALL_OFF"))
        
        return main_page
    
    def _get_device_status_text(self, device_id: str, primary_action: str) -> str:
        """Get current status text for device based on primary action."""
        # For now, return generic status - could be enhanced with real-time state
        if "toggle" in primary_action.lower():
            return "Toggle"
        elif "turnon" in primary_action.lower():
            return "Turn On"
        elif "turnoff" in primary_action.lower():
            return "Turn Off"
        else:
            return "Control"
    
    def _create_device_page(self, device_id: str, device_info: Dict[str, Any]) -> UiPage:
        """Create a dedicated page for a specific device with clear text labels."""
        device_name = device_info.get("name", f"Device {device_id}")
        device_type = device_info.get("type", "")
        actions = device_info.get("actions", [])
        clean_name = self._clean_command_name(device_name)
        
        page = UiPage(
            page_id=f"device_{device_id}",
            name=device_name,
            grid=Size(4, 6)
        )
        
        # Add device name as header
        page.add(create_ui_text(device_name, 0, 0, Size(4, 1)))
        
        # Group actions by type for organized layout
        action_groups = self._group_actions_by_type(actions)
        
        x, y = 0, 1  # Start after header
        
        # Add power controls first (row 1)
        power_actions = action_groups.get("power", [])
        for action in power_actions[:4]:  # Max 4 power buttons per row
            if x >= 4:
                break
            cmd = f"{clean_name}_{action}".upper()
            button_text = self._get_action_button_text(action)
            
            page.add(create_ui_text(button_text, x, y, Size(1, 1), cmd))
            x += 1
        
        # Move to next row
        if power_actions:
            x, y = 0, 2
        
        # Add level/speed controls (row 2-3)
        level_actions = action_groups.get("level", [])
        for action in level_actions:
            if y >= 5:  # Leave room for one more row
                break
            cmd = f"{clean_name}_{action}".upper()
            button_text = self._get_action_button_text(action)
            
            page.add(create_ui_text(button_text, x, y, Size(1, 1), cmd))
            
            x += 1
            if x >= 4:
                x = 0
                y += 1
        
        # Add light controls (next available row)
        light_actions = action_groups.get("light", [])
        if light_actions and y < 6:
            if x > 0:  # Start new row if we're not at beginning
                x = 0
                y += 1
            
            for action in light_actions:
                if y >= 6:
                    break
                cmd = f"{clean_name}_{action}".upper()
                button_text = self._get_action_button_text(action)
                
                page.add(create_ui_text(button_text, x, y, Size(1, 1), cmd))
                
                x += 1
                if x >= 4:
                    x = 0
                    y += 1
        
        # Add remaining actions
        other_actions = action_groups.get("other", [])
        for action in other_actions:
            if y >= 6:
                break
            cmd = f"{clean_name}_{action}".upper()
            button_text = self._get_action_button_text(action)
            
            # Fit remaining actions
            if x >= 4:
                x = 0
                y += 1
                if y >= 6:
                    break
            
            page.add(create_ui_text(button_text, x, y, Size(1, 1), cmd))
            x += 1
        
        return page
    
    def _get_action_button_text(self, action: str) -> str:
        """Get clear button text for an action."""
        action_lower = action.lower()
        
        # Power actions
        if action_lower == "turnon":
            return "Turn On"
        elif action_lower == "turnoff":
            return "Turn Off"
        elif action_lower == "togglepower":
            return "Power"
        elif action_lower == "toggle" and "light" not in action_lower:
            return "Toggle"
            
        # Light actions
        elif action_lower == "turnlighton":
            return "Light On"
        elif action_lower == "turnlightoff":
            return "Light Off"
        elif action_lower == "togglelight":
            return "Light"
            
        # Speed/Level actions
        elif action_lower == "increasespeed":
            return "Speed +"
        elif action_lower == "decreasespeed":
            return "Speed -"
        elif action_lower == "setspeed":
            return "Set Speed"
        elif action_lower == "increaseflame":
            return "Flame +"
        elif action_lower == "decreaseflame":
            return "Flame -"
        elif action_lower == "setflame":
            return "Set Flame"
        elif action_lower == "increasebright" or action_lower == "increasebrightness":
            return "Bright +"
        elif action_lower == "decreasebright" or action_lower == "decreasebrightness":
            return "Bright -"
        elif action_lower == "setbrightness":
            return "Set Bright"
            
        # Direction and other actions
        elif action_lower == "toggledirection":
            return "Direction"
        elif action_lower == "setdirection":
            return "Set Dir"
        elif action_lower == "settimer":
            return "Timer"
        elif action_lower == "stop":
            return "Stop"
        elif action_lower == "hold":
            return "Hold"
        elif action_lower == "preset":
            return "Preset"
        elif action_lower == "open":
            return "Open"
        elif action_lower == "close":
            return "Close"
        else:
            # Clean up action name for display (max 8 chars for button)
            cleaned = action.replace("Toggle", "").replace("Turn", "").replace("Set", "").replace("Increase", "+").replace("Decrease", "-")
            return cleaned[:8]
    
    def _group_actions_by_type(self, actions: List[str]) -> Dict[str, List[str]]:
        """Group actions by their type for better UI organization."""
        groups = {
            "power": [],
            "level": [],
            "light": [],
            "other": []
        }
        
        for action in actions:
            action_lower = action.lower()
            
            if any(keyword in action_lower for keyword in ["power", "turnon", "turnoff", "toggle"]) and "light" not in action_lower:
                groups["power"].append(action)
            elif any(keyword in action_lower for keyword in ["speed", "flame", "brightness", "increase", "decrease", "set"]) and "light" not in action_lower:
                groups["level"].append(action)
            elif "light" in action_lower:
                groups["light"].append(action)
            else:
                groups["other"].append(action)
        
        return groups
    
    def _get_device_icon(self, device_type: str) -> str:
        """Get appropriate icon for device type."""
        type_icons = {
            "CF": "uc:fan",           # Ceiling Fan
            "FP": "uc:fire",          # Fireplace
            "LT": "uc:lightbulb",     # Light
            "MS": "uc:window",        # Motorized Shades
            "GX": "uc:remote",        # Generic
            "BD": "uc:settings",      # Bidet
        }
        return type_icons.get(device_type, "uc:remote")
    
    def _get_primary_action(self, actions: List[str]) -> str:
        """Get the primary action for a device."""
        # Priority order for main button
        priority_actions = ["TogglePower", "TurnOn", "TurnOff", "Toggle"]
        
        for priority_action in priority_actions:
            if priority_action in actions:
                return priority_action
        
        # If no power action, return first action
        return actions[0] if actions else None

    async def _check_throttle(self, device_id: str) -> bool:
        """Check if command should be throttled for specific device."""
        import time
        
        current_time = time.time()
        
        # Global throttle - 100ms between any commands
        if current_time - self._global_throttle < 0.1:
            _LOG.debug("Global throttle active - 100ms between commands")
            return False
        
        # Device-specific throttle - 300ms between commands to same device
        last_time = self._device_throttle.get(device_id, 0)
        if current_time - last_time < 0.3:
            _LOG.debug(f"Device {device_id} throttle active - 300ms between device commands")
            return False
        
        # Update throttle times
        self._global_throttle = current_time
        self._device_throttle[device_id] = current_time
        return True

    async def cmd_handler(self, entity: ucapi.Entity, cmd_id: str, params: dict[str, Any] | None) -> ucapi.StatusCodes:
        """Handle remote commands."""
        _LOG.info("Remote command: %s %s", cmd_id, params)
        
        # Debug client state
        if not self._client:
            _LOG.error("Bond client is None!")
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE
            
        if not self._client.is_configured():
            _LOG.warning("Bond client not configured")
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE
        
        try:
            if cmd_id == Commands.ON:
                return await self._handle_on()
            elif cmd_id == Commands.OFF:
                return await self._handle_off()
            elif cmd_id == Commands.SEND_CMD:
                return await self._handle_send_cmd(params)
            else:
                _LOG.info("Unsupported remote command: %s", cmd_id)
                return ucapi.StatusCodes.NOT_IMPLEMENTED
                
        except Exception as e:
            _LOG.error("Error handling remote command %s: %s", cmd_id, e, exc_info=True)
            return ucapi.StatusCodes.SERVER_ERROR
    
    async def _handle_on(self) -> ucapi.StatusCodes:
        """Handle remote on command."""
        self._api.configured_entities.update_attributes(self.entity.id, {"state": States.ON})
        return ucapi.StatusCodes.OK
    
    async def _handle_off(self) -> ucapi.StatusCodes:
        """Handle remote off command.""" 
        self._api.configured_entities.update_attributes(self.entity.id, {"state": States.OFF})
        return ucapi.StatusCodes.OK
    
    async def _handle_send_cmd(self, params: dict[str, Any] | None) -> ucapi.StatusCodes:
        """Handle send command."""
        if not params or "command" not in params:
            _LOG.error("No command parameter provided")
            return ucapi.StatusCodes.BAD_REQUEST
        
        command = params["command"]
        _LOG.info(f"Executing Bond remote command: {command}")
        
        success = await self._execute_bond_command(command)
        return ucapi.StatusCodes.OK if success else ucapi.StatusCodes.SERVER_ERROR
    
    async def _execute_bond_command(self, command: str) -> bool:
        """Execute a Bond command on appropriate devices."""
        try:
            if not self._discovered_devices:
                _LOG.error("No discovered devices available")
                return False
            
            # Handle special commands
            if command == "NO_DEVICES":
                _LOG.warning("No devices command - cannot execute")
                return False
            
            # Handle global commands
            if command.startswith("ALL_"):
                return await self._execute_global_command(command)
            
            # Handle device-specific commands
            return await self._execute_device_command(command)
            
        except Exception as e:
            _LOG.error(f"Error executing Bond command {command}: {e}", exc_info=True)
            return False
    
    async def _execute_global_command(self, command: str) -> bool:
        """Execute a global command on all compatible devices."""
        action_map = {
            "ALL_ON": "TurnOn",
            "ALL_OFF": "TurnOff", 
            "ALL_TOGGLE": "TogglePower"
        }
        
        bond_action = action_map.get(command)
        if not bond_action:
            _LOG.error(f"Unknown global command: {command}")
            return False
        
        success_count = 0
        tasks = []
        
        # Execute all commands in parallel
        for device_id, device_info in self._discovered_devices.items():
            actions = device_info.get("actions", [])
            if bond_action in actions:
                task = self._execute_device_action_safe(device_id, bond_action, device_info.get('name'))
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
        
        _LOG.info(f"Global command {command} executed on {success_count}/{len(tasks)} devices")
        return success_count > 0
    
    async def _execute_device_action_safe(self, device_id: str, action: str, device_name: str) -> bool:
        """Safely execute an action on a device with error handling."""
        try:
            device_success = await self._client.execute_action(device_id, action)
            if device_success:
                _LOG.info(f"Executed {action} on device {device_name}")
                return True
            else:
                _LOG.warning(f"Failed to execute {action} on device {device_name}")
                return False
        except Exception as e:
            _LOG.error(f"Error executing {action} on device {device_name}: {e}")
            return False
    
    async def _execute_device_command(self, command: str) -> bool:
        """Execute a command on a specific device."""
        success = False
        
        for device_id, device_info in self._discovered_devices.items():
            device_name = device_info.get("name", f"Device_{device_id}")
            device_prefix = self._clean_command_name(device_name)
            
            if command.startswith(device_prefix + "_"):
                # Check throttling for this specific device
                if not await self._check_throttle(device_id):
                    _LOG.debug(f"Command {command} throttled for device {device_name}")
                    # Return OK to avoid showing error, but don't execute
                    return True
                
                # Extract action part
                action_part = command[len(device_prefix)+1:]  # +1 for underscore
                _LOG.debug(f"Device: {device_name}, Prefix: {device_prefix}, Action: {action_part}")
                
                # Map action to Bond API action
                available_actions = device_info.get("actions", [])
                bond_action_result = self._map_ui_action_to_bond_action(action_part, available_actions)
                
                if bond_action_result:
                    bond_action = bond_action_result
                    argument = None
                    
                    # Handle actions with arguments
                    if isinstance(bond_action_result, tuple):
                        bond_action, argument = bond_action_result
                    else:
                        # Get default argument for actions that need it
                        argument = self._get_default_argument(bond_action, device_info)
                    
                    try:
                        _LOG.info(f"Executing Bond API call: device_id={device_id}, action={bond_action}, argument={argument}")
                        device_success = await self._client.execute_action(device_id, bond_action, argument)
                        if device_success:
                            success = True
                            _LOG.info(f"Successfully executed {bond_action} on device {device_info.get('name')}")
                        else:
                            _LOG.error(f"Bond API returned failure for {bond_action} on device {device_info.get('name')}")
                    except Exception as e:
                        _LOG.error(f"Exception executing {bond_action} on device {device_info.get('name')}: {e}", exc_info=True)
                    break
                else:
                    _LOG.error(f"Could not map action '{action_part}' to any Bond action for device {device_name}")
                    _LOG.debug(f"Available actions for {device_name}: {available_actions}")
        
        if not success:
            _LOG.warning(f"Could not execute command: {command}")
        
        return success
    
    def _get_default_argument(self, bond_action: str, device_info: Dict[str, Any]) -> Optional[Union[int, str]]:
        """Get default argument for actions that require them."""
        device_type = device_info.get("type", "")
        
        # Actions that need arguments
        if bond_action == "SetSpeed":
            # Default to speed 3 (medium) for ceiling fans
            return 3
        elif bond_action == "SetFlame":
            # Default to 50% flame for fireplaces
            return 50
        elif bond_action == "SetBrightness":
            # Default to 75% brightness for lights
            return 75
        elif bond_action == "SetDirection":
            # Default to forward (1) for ceiling fans
            return 1
        elif bond_action == "SetTimer":
            # Default to 60 minutes
            return 60
        
        # No argument needed
        return None
    
    def _map_ui_action_to_bond_action(self, ui_action: str, available_actions: List[str] = None) -> Optional[Union[str, tuple]]:
        """Map UI action to Bond API action."""
        if available_actions is None:
            # Get all available actions from all devices
            available_actions = set()
            for device_info in self._discovered_devices.values():
                available_actions.update(device_info.get("actions", []))
            available_actions = list(available_actions)
        
        _LOG.debug(f"Mapping UI action '{ui_action}' from available actions: {available_actions}")
        
        # Direct match first (case sensitive)
        if ui_action in available_actions:
            _LOG.debug(f"Direct match found: {ui_action}")
            return ui_action
        
        # Common mappings
        action_map = {
            "TURNON": "TurnOn",
            "TURNOFF": "TurnOff",
            "TOGGLEPOWER": "TogglePower",
            "TOGGLE": "TogglePower",
            "TURNLIGHTON": "TurnLightOn",
            "TURNLIGHTOFF": "TurnLightOff",
            "TOGGLELIGHT": "ToggleLight",
            "INCREASESPEED": "IncreaseSpeed",
            "DECREASESPEED": "DecreaseSpeed",
            "SETSPEED": "SetSpeed",
            "INCREASEFLAME": "IncreaseFlame",
            "DECREASEFLAME": "DecreaseFlame",
            "SETFLAME": "SetFlame",
            "INCREASEBRIGHT": "IncreaseBrightness",
            "DECREASEBRIGHT": "DecreaseBrightness",
            "SETBRIGHTNESS": "SetBrightness",
            "SETTIMER": "SetTimer",
            "SETDIRECTION": "SetDirection",
            "TOGGLEDIRECTION": "ToggleDirection",
            "STOP": "Stop"
        }
        
        mapped = action_map.get(ui_action)
        if mapped and mapped in available_actions:
            _LOG.debug(f"Mapped action found: {ui_action} -> {mapped}")
            return mapped
        
        # Try partial matches (case insensitive)
        ui_lower = ui_action.lower()
        for bond_action in available_actions:
            if ui_lower in bond_action.lower() or bond_action.lower() in ui_lower:
                _LOG.debug(f"Partial match found: {ui_action} -> {bond_action}")
                return bond_action
        
        _LOG.warning(f"Could not map UI action '{ui_action}' to any available Bond action: {available_actions}")
        return None