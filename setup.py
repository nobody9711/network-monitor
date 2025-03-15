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
                "unbound",
                "python3-pip",
                "python3-venv",
                "git",
                "gnupg",
                "curl",
                "apt-transport-https",
                "software-properties-common"
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
        
        # Add GitHub configuration
        self.github_repo = "https://github.com/nobody9711/network-monitor.git"
        self.github_branch = "main"
    
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
            
            # First install basic requirements
            commands = [
                ["sudo", "apt", "update"],
                ["sudo", "apt", "install", "-y"] + packages
            ]
            
            for cmd in commands:
                code, output = self._run_command(cmd)
                if code != 0:
                    logger.error(f"Failed to install system packages: {output}")
                    return False
            
            # Add MongoDB repository
            logger.info("Adding MongoDB repository...")
            try:
                # Import MongoDB public key
                key_cmd = ["wget", "-qO", "-", "https://www.mongodb.org/static/pgp/server-7.0.asc", "|", "sudo", "apt-key", "add", "-"]
                code, output = self._run_command(key_cmd)
                if code != 0:
                    logger.error(f"Failed to download MongoDB key: {output}")
                    return False
                
                # Add MongoDB repository based on OS version
                os_version = ""
                try:
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("VERSION_CODENAME="):
                                os_version = line.split("=")[1].strip().strip('"')
                                break
                except Exception:
                    os_version = "bullseye"  # Default to Debian 11/Raspberry Pi OS
                
                repo_content = f"deb http://repo.mongodb.org/apt/debian {os_version}/mongodb-org/7.0 main"
                with open("/tmp/mongodb-org-7.0.list", "w") as f:
                    f.write(repo_content)
                
                mv_cmd = ["sudo", "mv", "/tmp/mongodb-org-7.0.list", "/etc/apt/sources.list.d/"]
                code, output = self._run_command(mv_cmd)
                if code != 0:
                    logger.error(f"Failed to add MongoDB repository: {output}")
                    return False
            except Exception as e:
                logger.error(f"Failed to set up MongoDB repository: {e}")
                return False
            
            # Add InfluxDB repository
            logger.info("Adding InfluxDB repository...")
            try:
                # Import InfluxDB public key
                key_cmd = ["wget", "-qO", "-", "https://repos.influxdata.com/influxdata-archive_compat.key", "|", "sudo", "apt-key", "add", "-"]
                code, output = self._run_command(key_cmd)
                if code != 0:
                    logger.error(f"Failed to download InfluxDB key: {output}")
                    return False
                
                # Add InfluxDB repository
                repo_content = "deb https://repos.influxdata.com/debian stable main"
                with open("/tmp/influxdb.list", "w") as f:
                    f.write(repo_content)
                
                mv_cmd = ["sudo", "mv", "/tmp/influxdb.list", "/etc/apt/sources.list.d/"]
                code, output = self._run_command(mv_cmd)
                if code != 0:
                    logger.error(f"Failed to add InfluxDB repository: {output}")
                    return False
            except Exception as e:
                logger.error(f"Failed to set up InfluxDB repository: {e}")
                return False
            
            # Update package list and install MongoDB and InfluxDB
            logger.info("Installing MongoDB and InfluxDB...")
            commands = [
                ["sudo", "apt", "update"],
                ["sudo", "apt", "install", "-y", "mongodb-org"],
                ["sudo", "apt", "install", "-y", "influxdb"]
            ]
            
            for cmd in commands:
                code, output = self._run_command(cmd)
                if code != 0:
                    logger.error(f"Failed to install package: {output}")
                    logger.info("Attempting alternative package names...")
                    
                    # Try alternative package names
                    if "mongodb-org" in cmd:
                        alt_cmd = ["sudo", "apt", "install", "-y", "mongodb"]
                        code, output = self._run_command(alt_cmd)
                        if code != 0:
                            logger.error(f"Failed to install MongoDB: {output}")
                            return False
                    elif "influxdb" in cmd:
                        alt_cmd = ["sudo", "apt", "install", "-y", "influxdb2"]
                        code, output = self._run_command(alt_cmd)
                        if code != 0:
                            logger.error(f"Failed to install InfluxDB: {output}")
                            return False
            
            # Enable and start services
            logger.info("Enabling and starting services...")
            services = [("mongodb", "mongod"), ("influxdb", "influxdb")]
            for service_name, service_unit in services:
                commands = [
                    ["sudo", "systemctl", "daemon-reload"],
                    ["sudo", "systemctl", "enable", service_unit],
                    ["sudo", "systemctl", "start", service_unit]
                ]
                
                for cmd in commands:
                    code, output = self._run_command(cmd)
                    if code != 0:
                        logger.warning(f"Failed to configure {service_name} service: {output}")
                        # Try alternative service name
                        alt_cmd = [cmd[0], cmd[1], cmd[2], service_name]
                        code, output = self._run_command(alt_cmd)
                        if code != 0:
                            logger.error(f"Failed to configure {service_name} service with alternative name: {output}")
                            return False
            
            return True
        
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
    
    def update_github(self) -> bool:
        """Update GitHub repository with latest changes."""
        try:
            logger.info("Updating GitHub repository...")
            
            # Check if git is initialized
            if not (self.base_dir / ".git").exists():
                logger.info("Initializing git repository...")
                code, output = self._run_command(["git", "init"])
                if code != 0:
                    logger.error(f"Failed to initialize git repository: {output}")
                    return False
                
                # Configure git if not already configured
                code, output = self._run_command(["git", "config", "user.name"])
                if code != 0:
                    code, _ = self._run_command(["git", "config", "--global", "user.name", "nobody9711"])
                    if code != 0:
                        logger.error("Failed to configure git username")
                        return False
                
                code, output = self._run_command(["git", "config", "user.email"])
                if code != 0:
                    code, _ = self._run_command(["git", "config", "--global", "user.email", "jordanjohnson974@gmail.com"])
                    if code != 0:
                        logger.error("Failed to configure git email")
                        return False
            
            # Check if remote exists
            code, output = self._run_command(["git", "remote"])
            if "origin" not in (output or ""):
                logger.info("Adding GitHub remote...")
                code, output = self._run_command(["git", "remote", "add", "origin", self.github_repo])
                if code != 0:
                    logger.error(f"Failed to add GitHub remote: {output}")
                    return False
            
            # Add all changes
            logger.info("Adding changes...")
            code, output = self._run_command(["git", "add", "."])
            if code != 0:
                logger.error(f"Failed to add changes: {output}")
                return False
            
            # Commit changes
            logger.info("Committing changes...")
            commit_msg = "Update from setup script: " + ", ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Update from setup script"
            code, output = self._run_command(["git", "commit", "-m", commit_msg])
            if code != 0 and "nothing to commit" not in (output or ""):
                logger.error(f"Failed to commit changes: {output}")
                return False
            
            # Push changes
            logger.info("Pushing changes to GitHub...")
            code, output = self._run_command(["git", "push", "-u", "origin", self.github_branch])
            if code != 0:
                logger.error(f"Failed to push changes: {output}")
                return False
            
            logger.info("GitHub repository updated successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update GitHub repository: {e}")
            return False
    
    def run_setup(self) -> bool:
        """Run the complete setup process."""
        logger.info("Starting Network Monitor setup...")
        
        success = (
            self.check_python_version()
            and self.install_system_packages(self.check_system_packages())
            and self.setup_virtual_environment()
            and self.install_python_packages()
            and self.setup_directories()
            and self.start_services(self.check_services())
            and self.create_config()
        )
        
        if success:
            logger.info("Setup completed successfully!")
            
            # Update GitHub repository
            if not self.update_github():
                logger.warning("Setup completed but failed to update GitHub repository")
            
            return True
        else:
            return False

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