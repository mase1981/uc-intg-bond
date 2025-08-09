# Bond Integration for Unfolded Circle Remote

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![GitHub release](https://img.shields.io/github/v/release/mase1981/uc-intg-bond.svg)](https://github.com/mase1981/uc-intg-bond/releases)

Control your Bond-connected ceiling fans, fireplaces, and other RF/IR devices directly from your Unfolded Circle Remote.

## Features

- **PIN-based Authentication**: Secure setup using your Bond device's PIN
- **Auto-discovery**: Automatically find Bond hubs on your local network
- **Full Device Support**: Control ceiling fans, fireplaces, motorized shades, lights, and more
- **Device-specific UI**: Customized control pages based on device type with clear text labels
- **Real-time Control**: Direct communication with Bond Local API
- **Command Throttling**: Prevents rapid-fire commands that could cause errors
- **Multiple Deployment Options**: Install via tar.gz or Docker

## Supported Devices

- **Ceiling Fans (CF)**: Power, speed control, direction, light control
- **Fireplaces (FP)**: Power, flame control, fan control
- **Motorized Shades (MS)**: Open/close, position control
- **Lights (LT)**: On/off, brightness control
- **Generic devices (GX)**: Basic power and available action controls

## Requirements

- Unfolded Circle Remote with firmware 1.7.0 or later
- Bond hub (Bridge or Smart by Bond devices) on the same local network
- Bond hub firmware v2.0 or later
- Bond device PIN (found on device label)

## Quick Start

### Method 1: Install from Release (Recommended)

1. Download the latest `uc-intg-bond-vX.X.X.tar.gz` from [Releases](https://github.com/mase1981/uc-intg-bond/releases)
2. Open your Remote's web configurator
3. Navigate to **Integrations** → **Add Integration**
4. Upload the downloaded tar.gz file
5. Follow the setup wizard:
   - Enter your Bond hub IP address (e.g., `192.168.1.100`)
   - Enter the 4-digit PIN from your Bond device label
6. Integration will unlock your Bond device, discover devices, and create remote controls

### Method 2: Docker Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mase1981/uc-intg-bond.git
   cd uc-intg-bond
   ```

2. **Create required directories**:
   ```bash
   mkdir -p config logs
   ```

3. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Configure via Remote**:
   - Add integration in Remote web configurator
   - Point to `http://your-docker-host:9090`
   - Complete setup with Bond IP and PIN

5. **Check logs**:
   ```bash
   docker-compose logs -f bond-integration
   ```

## Setup Process

### Finding Your Bond IP Address

The integration will attempt auto-discovery, but you can also find your Bond IP manually:

1. **Router Admin Panel**: Check connected devices. For best results give your bond hub a static IP
2. **Bond App**: Look in device settings
3. **Network Scanner**: Use tools like Advanced IP Scanner
4. **Command Line**:
   ```bash
   # Windows
   arp -a | findstr "b0-ce-18"
   
   # Linux/Mac
   arp -a | grep "b0:ce:18"
   ```

### Finding Your Bond PIN

Look for a 4-digit number on a sticker on your Bond device (usually on the bottom or back).

### Authentication Process

1. **PIN Entry**: Enter your Bond IP and PIN during setup
2. **Automatic Unlock**: Integration unlocks your Bond device using the PIN
3. **Token Retrieval**: A secure token is obtained and stored for future use
4. **Device Discovery**: All configured devices are automatically discovered

### Troubleshooting Setup

**Bond Device Locked**: If your Bond device is locked and no PIN works:
1. Power cycle your Bond device (unplug for 10 seconds)
2. Within 10 minutes, retry setup - device will be temporarily unlocked
3. Complete setup during this window

## Usage

### Remote Control

The integration creates a remote entity with multiple pages:

1. **Main Page**: Overview with all devices and quick controls
2. **Device Pages**: Individual pages for each device with all available controls

### Button Layout

- **Main Page**: Device names above control buttons ("Turn On", "Turn Off", "Toggle")
- **Device Pages**: Organized controls grouped by function:
  - **Power Controls**: Turn On, Turn Off, Power Toggle
  - **Level Controls**: Speed +/-, Flame +/-, Brightness +/-
  - **Light Controls**: Light On/Off, Light Toggle
  - **Other Controls**: Direction, Timer, Stop, etc.

### Physical Button Mapping

- **Power Button**: Primary device power toggle
- **Volume Up/Down**: Fan speed or level control
- **Channel Buttons**: Available for custom mapping

## Configuration

Configuration is automatically saved to `config.json`:

```json
{
  "bond_ip": "192.168.1.100",
  "bond_token": "your_secure_token",
  "bond_name": "Bond Hub",
  "polling_interval": 30,
  "devices": {
    "device_id": {
      "name": "Living Room Fan",
      "type": "CF",
      "actions": ["TurnOn", "TurnOff", "SetSpeed", "ToggleLight"]
    }
  }
}
```

## Development

### Local Development Setup

1. **Prerequisites**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run integration**:
   ```bash
   python -m uc_intg_bond.driver
   ```

4. **Debug mode**:
   ```bash
   export UC_LOG_LEVEL=DEBUG
   python -m uc_intg_bond.driver
   ```

### Building Docker Image

```bash
# Build image
docker build -t uc-intg-bond:latest .

# Run container
docker run -d \
  --name uc-intg-bond \
  -p 9090:9090 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  uc-intg-bond:latest
```

## API Reference

This integration uses the Bond Local HTTP API v2. For detailed API documentation:
- [Bond Local API Documentation](https://docs-local.appbond.com/)

## Troubleshooting

### Common Issues

**Connection Issues**:
- Ensure Bond hub and Remote are on the same network
- Verify Bond IP address is correct
- Check firewall settings

**Authentication Issues**:
- Verify PIN from device label (4 digits)
- Try power cycling Bond device if locked
- Complete setup within 10 minutes of power cycle

**Device Not Responding**:
- Check Bond hub connection to device in Bond app
- Verify device is properly configured in Bond app
- Restart integration if devices changed

**Command Errors**:
- Commands are throttled to prevent rapid-fire (1 second minimum)
- Check logs for specific error messages
- Verify device supports the requested action

### Debug Logging

Enable debug logging to troubleshoot issues:

```bash
# Environment variable
export UC_LOG_LEVEL=DEBUG

# Or check integration logs in Remote web configurator
```

### Log Locations

- **Remote Integration**: Check via Remote web configurator
- **Docker**: `docker-compose logs -f bond-integration`
- **Local Dev**: Console output

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest`
5. Format code: `black uc_intg_bond && isort uc_intg_bond`
6. Submit a pull request

## License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Unfolded Circle](https://unfoldedcircle.com/) for the Remote and integration framework
- [Bond](https://bondhome.io/) for their comprehensive local API
- The Unfolded Circle community for feedback and testing

## Support

- **Issues**: [GitHub Issues](https://github.com/mase1981/uc-intg-bond/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mase1981/uc-intg-bond/discussions)
- **Community**: [Unfolded Circle Community](https://community.unfoldedcircle.com/)

**Hope you enjoy this integration, thank you: Meir Miyara.**
