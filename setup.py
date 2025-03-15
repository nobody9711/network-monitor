#!/usr/bin/env python3
"""
Network Monitor Setup Script
Checks and installs all required dependencies and configurations.
"""

import os
import sys
import subprocess
import platform
import shutil
import logging
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SetupManager:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.is_raspberry_pi = self._check_raspberry_pi()
        self.python_version = sys.version_info
        self.base_dir = Path(__file__).parent.absolute()
        
        # Define required system packages
        self.system_packages = {
            "linux": [
                "nmap",
                "mongodb",
                "influxdb",
                "unbound",
                "python3-pip",
                "python3-venv",
                "git"
            ],
            "windows": [
                "nmap",
                "mongodb",
                "influxdb",
                "unbound"
            ]
        }
        
        # Define required Python packages
        self.python_packages = [
            "flask",
            "dash",
            "dash-bootstrap-components",
            "plotly",
            "influxdb-client",
            "pymongo",
            "psutil",
            "python-nmap",
            "netifaces",
            "requests",
            "python-dateutil",
            "humanize",
            "schedule",
            "python-json-logger"
        ]
        
        # Add platform-specific Python packages
        if self.is_raspberry_pi:
            self.python_packages.extend([
                "rpi.gpio",
                "smbus2",
                "gpiozero"
            ])
    
    def _check_raspberry_pi(self) -> bool:
        """Check if running on a Raspberry Pi."""
        try:
            with open("/proc/device-tree/model", "r") as f:
                return "raspberry pi" in f.read().lower()
        except Exception:
            return False
    
    def _run_command(self, command: List[str], check_output: bool = False) -> Tuple[int, Optional[str]]:
        """Run a command and return exit code and output."""
        try:
            if check_output:
                output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
                return 0, output
            else:
                process = subprocess.run(command, capture_output=True, text=True)
                return process.returncode, process.stdout
        except subprocess.CalledProcessError as e:
            return e.returncode, e.output
        except Exception as e:
            return 1, str(e)
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        min_version = (3, 8)
        if self.python_version < min_version:
            logger.error(f"Python version {'.'.join(map(str, self.python_version[:3]))} is not supported. "
                        f"Please use Python {'.'.join(map(str, min_version))} or higher.")
            return False
        return True
    
    def check_system_packages(self) -> List[str]:
        """Check which system packages are missing."""
        missing_packages = []
        
        if self.os_type == "linux":
            # Use apt to check installed packages
            for package in self.system_packages["linux"]:
                code, _ = self._run_command(["dpkg", "-l", package])
                if code != 0:
                    missing_packages.append(package)
        
        elif self.os_type == "windows":
            # Check Windows packages using where command
            for package in self.system_packages["windows"]:
                code, _ = self._run_command(["where", package])
                if code != 0:
                    missing_packages.append(package)
        
        return missing_packages
    
    def install_system_packages(self, packages: List[str]) -> bool:
        """Install missing system packages."""
        if not packages:
            return True
        
        if self.os_type == "linux":
            logger.info("Installing system packages with apt...")
            commands = [
                ["sudo", "apt", "update"],
                ["sudo", "apt", "install", "-y"] + packages
            ]
            
            for cmd in commands:
                code, output = self._run_command(cmd)
                if code != 0:
                    logger.error(f"Failed to install system packages: {output}")
                    return False
        
        elif self.os_type == "windows":
            logger.info("Please install the following packages manually:")
            logger.info("1. MongoDB: https://www.mongodb.com/try/download/community")
            logger.info("2. InfluxDB: https://portal.influxdata.com/downloads/")
            logger.info("3. Nmap: https://nmap.org/download.html")
            logger.info("4. Unbound: https://nlnetlabs.nl/projects/unbound/download/")
            return False
        
        return True
    
    def setup_virtual_environment(self) -> bool:
        """Create and activate virtual environment."""
        venv_path = self.base_dir / "venv"
        
        if not venv_path.exists():
            logger.info("Creating virtual environment...")
            code, output = self._run_command([sys.executable, "-m", "venv", str(venv_path)])
            if code != 0:
                logger.error(f"Failed to create virtual environment: {output}")
                return False
        
        # Get path to pip in virtual environment
        if self.os_type == "windows":
            pip_path = venv_path / "Scripts" / "pip.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
        
        # Upgrade pip
        code, output = self._run_command([str(pip_path), "install", "--upgrade", "pip"])
        if code != 0:
            logger.error(f"Failed to upgrade pip: {output}")
            return False
        
        return True
    
    def install_python_packages(self) -> bool:
        """Install required Python packages."""
        # Get path to pip in virtual environment
        venv_path = self.base_dir / "venv"
        if self.os_type == "windows":
            pip_path = venv_path / "Scripts" / "pip.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
        
        logger.info("Installing Python packages...")
        code, output = self._run_command([str(pip_path), "install", "-r", "requirements.txt"])
        if code != 0:
            logger.error(f"Failed to install Python packages: {output}")
            return False
        
        return True
    
    def setup_directories(self) -> bool:
        """Create necessary directories."""
        directories = {
            "linux": [
                "/var/log/network-monitor",
                "/tmp/network-monitor"
            ],
            "windows": [
                os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\logs"),
                os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\temp")
            ]
        }
        
        for directory in directories[self.os_type]:
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                return False
        
        return True
    
    def check_services(self) -> Dict[str, bool]:
        """Check if required services are running."""
        services = {
            "mongodb": False,
            "influxdb": False,
            "unbound": False
        }
        
        if self.os_type == "linux":
            for service in services:
                code, _ = self._run_command(["systemctl", "is-active", "--quiet", service])
                services[service] = code == 0
        
        elif self.os_type == "windows":
            for service in services:
                code, _ = self._run_command(["sc", "query", service])
                services[service] = code == 0
        
        return services
    
    def start_services(self, services: Dict[str, bool]) -> bool:
        """Start required services that are not running."""
        for service, running in services.items():
            if not running:
                logger.info(f"Starting {service}...")
                
                if self.os_type == "linux":
                    commands = [
                        ["sudo", "systemctl", "enable", service],
                        ["sudo", "systemctl", "start", service]
                    ]
                    
                    for cmd in commands:
                        code, output = self._run_command(cmd)
                        if code != 0:
                            logger.error(f"Failed to start {service}: {output}")
                            return False
                
                elif self.os_type == "windows":
                    code, output = self._run_command(["net", "start", service])
                    if code != 0:
                        logger.error(f"Failed to start {service}: {output}")
                        return False
        
        return True
    
    def create_config(self) -> bool:
        """Create initial configuration file if it doesn't exist."""
        config_path = self.base_dir / "config.yml"
        example_config_path = self.base_dir / "config.example.yml"
        
        if not config_path.exists() and example_config_path.exists():
            try:
                shutil.copy(example_config_path, config_path)
                logger.info("Created initial configuration file from example")
                logger.info("Please edit config.yml with your specific settings")
                return True
            except Exception as e:
                logger.error(f"Failed to create configuration file: {e}")
                return False
        
        return True
    
    def run_setup(self) -> bool:
        """Run the complete setup process."""
        logger.info("Starting Network Monitor setup...")
        
        # Check Python version
        if not self.check_python_version():
            return False
        
        # Check and install system packages
        missing_packages = self.check_system_packages()
        if missing_packages:
            logger.info(f"Missing system packages: {', '.join(missing_packages)}")
            if not self.install_system_packages(missing_packages):
                return False
        
        # Setup virtual environment
        if not self.setup_virtual_environment():
            return False
        
        # Install Python packages
        if not self.install_python_packages():
            return False
        
        # Create necessary directories
        if not self.setup_directories():
            return False
        
        # Check and start services
        services = self.check_services()
        if not all(services.values()):
            logger.info("Some services are not running")
            if not self.start_services(services):
                return False
        
        # Create initial configuration
        if not self.create_config():
            return False
        
        logger.info("Setup completed successfully!")
        return True

def main():
    setup = SetupManager()
    if setup.run_setup():
        logger.info("""
Network Monitor setup completed successfully!

To start the application:
1. Edit config.yml with your specific settings
2. Activate the virtual environment:
   - Windows: .\\venv\\Scripts\\activate
   - Linux: source venv/bin/activate
3. Run the application:
   python src/main.py

For more information, please refer to the README.md file.
""")
        sys.exit(0)
    else:
        logger.error("Setup failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 