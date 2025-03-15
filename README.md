# Network Monitor

A comprehensive network monitoring tool for Raspberry Pi and Windows systems, featuring integration with Pi-hole and Unbound DNS.

## Features

- Real-time network monitoring and bandwidth tracking
- Device discovery and management
- System performance metrics
- Security analysis and alerts
- Integration with Pi-hole and Unbound
- Modern web dashboard
- Cross-platform support (Raspberry Pi and Windows)

## Requirements

### Raspberry Pi / Linux
- Raspberry Pi 5 (recommended) or compatible Linux system
- Debian 12 Bookworm or compatible distribution
- Python 3.8 or higher
- MongoDB
- InfluxDB
- Unbound DNS resolver
- Nmap

### Windows
- Windows 10/11
- Python 3.8 or higher
- MongoDB
- InfluxDB
- Unbound DNS resolver
- Nmap

## Quick Start

### Automated Installation

#### On Raspberry Pi / Linux:
```bash
# Clone the repository
git clone https://github.com/nobody9711/network-monitor.git
cd network-monitor

# Make the setup script executable
chmod +x setup.sh

# Run the setup script (requires sudo)
sudo ./setup.sh
```

#### On Windows:
```powershell
# Clone the repository
git clone https://github.com/nobody9711/network-monitor.git
cd network-monitor

# Run the setup script as Administrator
# Right-click setup.ps1 and select "Run as Administrator"
# Or from an Administrator PowerShell:
.\setup.ps1
```

The setup scripts will:
1. Check and install system requirements
2. Set up Python virtual environment
3. Install Python dependencies
4. Configure necessary services
5. Create required directories
6. Generate initial configuration

### Manual Installation

If you prefer to install manually or the automated setup fails:

1. Install system dependencies:
   - MongoDB: [Download](https://www.mongodb.com/try/download/community)
   - InfluxDB: [Download](https://portal.influxdata.com/downloads/)
   - Unbound: [Download](https://nlnetlabs.nl/projects/unbound/download/)
   - Nmap: [Download](https://nmap.org/download.html)

2. Set up Python environment:
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   .\venv\Scripts\activate
   # On Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. Configure the application:
   ```bash
   # Copy example configuration
   cp config.example.yml config.yml
   # Edit config.yml with your settings
   ```

## Configuration

The `config.yml` file contains all configuration options:

- System settings (logging, paths)
- Network settings (interfaces, scan intervals)
- Security settings (alert thresholds, email notifications)
- Database settings (MongoDB, InfluxDB)
- Dashboard settings (port, authentication)
- Integration settings (Pi-hole, Unbound)
- Platform-specific settings (Raspberry Pi GPIO, Windows services)

## Usage

1. Start the application:
   ```bash
   # Activate virtual environment if not already active
   source venv/bin/activate  # or .\venv\Scripts\activate on Windows
   
   # Run the application
   python src/main.py
   ```

2. Access the dashboard:
   - Open a web browser
   - Navigate to `http://localhost:8050` (or your configured port)
   - Log in with your configured credentials

## Development

- Python 3.8+ required
- Use Black for code formatting
- Follow PEP 8 style guide
- Run tests with pytest

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Open an issue for bug reports or feature requests
- Check existing issues before creating new ones
- Provide detailed information when reporting issues

## Acknowledgments

- Dash and Plotly for the dashboard framework
- MongoDB and InfluxDB for data storage
- Pi-hole and Unbound projects
- Python WMI and psutil libraries 