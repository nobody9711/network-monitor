# Network Monitor

A comprehensive network monitoring tool designed for Windows 11 and Raspberry Pi systems. This tool provides real-time monitoring of network traffic, device tracking, and system performance metrics with a modern web dashboard.

## Features

- Real-time network monitoring and bandwidth tracking
- Device discovery and tracking
- System performance monitoring (CPU, Memory, Disk, Temperature)
- Security analysis and alerts
- Modern web dashboard with real-time updates
- Support for both Windows 11 and Raspberry Pi systems
- Integration with Pi-hole and Unbound DNS (optional)

## Requirements

### Windows 11
- Python 3.9 or higher
- MongoDB (local or remote)
- InfluxDB 2.x (local or remote)
- Nmap for network scanning
- Administrator privileges for WMI access

### Optional Components
- Pi-hole for DNS monitoring
- Unbound DNS resolver

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/network-monitor.git
cd network-monitor
```

2. Create a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Nmap:
- Download and install Nmap from https://nmap.org/download.html
- Add Nmap to your system PATH

5. Configure the application:
```bash
copy config.example.yml config.yml
# Edit config.yml with your settings
```

## Configuration

Edit `config.yml` to set up:

- MongoDB connection details
- InfluxDB connection details
- Network scanning settings
- Alert thresholds
- Email notifications (optional)
- Pi-hole integration (optional)
- Unbound integration (optional)

## Running the Application

1. Start the monitoring service:
```bash
python src/main.py
```

2. Access the dashboard:
- Open your browser and navigate to `http://localhost:8050`
- Default credentials: admin/admin

## Dashboard Features

- Overview of network status
- Real-time bandwidth graphs
- Active device list with details
- System performance metrics
- Security alerts and notifications
- Network interface statistics
- DNS query analytics (if Pi-hole is configured)

## Security Features

- Network device tracking
- Port scan detection
- Bandwidth anomaly detection
- New device alerts
- Suspicious activity monitoring
- Email notifications for security events

## Windows-Specific Features

- WMI integration for detailed system metrics
- Network adapter monitoring
- SMART disk information
- Temperature monitoring (if supported by hardware)
- Windows Event Log integration

## Troubleshooting

### Common Issues

1. WMI Access Denied
```
Solution: Run the application as Administrator or grant WMI permissions to your user
```

2. Nmap Not Found
```
Solution: Ensure Nmap is installed and added to system PATH
```

3. Temperature Data Not Available
```
Solution: Temperature monitoring depends on hardware support and WMI access
```

### Logs

- Application logs are stored in `logs/network-monitor.log`
- Set log level in `config.yml` (default: INFO)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Dash and Plotly for the dashboard framework
- MongoDB and InfluxDB for data storage
- Pi-hole and Unbound projects
- Python WMI and psutil libraries 