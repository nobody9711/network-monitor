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
    
    def _run_mongodb_diagnostics(self) -> bool:
        """Run comprehensive MongoDB diagnostics."""
        logger.info("Running MongoDB diagnostics...")
        
        try:
            # 1. Check MongoDB package status
            code, pkg_status = self._run_command(["dpkg", "-l", "mongodb*"])
            if code == 0:
                logger.info(f"Installed MongoDB packages:\n{pkg_status}")
            
            # 2. Check repository configuration
            code, repo_status = self._run_command(["cat", "/etc/apt/sources.list.d/mongodb-org-7.0.list"])
            logger.info(f"MongoDB repository configuration:\n{repo_status}")
            
            # 3. Check data directory
            data_dirs = ["/var/lib/mongodb", "/var/lib/mongo"]
            for data_dir in data_dirs:
                if os.path.exists(data_dir):
                    # Check directory permissions
                    code, perms = self._run_command(["ls", "-la", data_dir])
                    logger.info(f"MongoDB data directory {data_dir} permissions:\n{perms}")
                    
                    # Check directory ownership
                    code, owner = self._run_command(["stat", "-c", "%U:%G", data_dir])
                    logger.info(f"MongoDB data directory {data_dir} owner: {owner}")
                    
                    # Fix permissions if needed
                    if "mongodb:mongodb" not in owner.strip():
                        logger.info(f"Fixing {data_dir} ownership...")
                        self._run_command(["sudo", "chown", "-R", "mongodb:mongodb", data_dir])
                        self._run_command(["sudo", "chmod", "-R", "755", data_dir])
            
            # 4. Check log file
            log_file = "/var/log/mongodb/mongod.log"
            if os.path.exists(log_file):
                code, logs = self._run_command(["sudo", "tail", "-n", "20", log_file])
                logger.info(f"Recent MongoDB logs:\n{logs}")
            
            # 5. Check systemd service status
            code, service_status = self._run_command(["systemctl", "status", "mongod"])
            logger.info(f"MongoDB service status:\n{service_status}")
            
            # 6. Check system resources
            code, mem_info = self._run_command(["free", "-h"])
            logger.info(f"System memory status:\n{mem_info}")
            
            code, disk_info = self._run_command(["df", "-h", "/var/lib/mongodb"])
            logger.info(f"Disk space status:\n{disk_info}")
            
            # 7. Try to fix common issues
            logger.info("Attempting to fix common issues...")
            
            # Ensure MongoDB user exists
            code, _ = self._run_command(["id", "mongodb"])
            if code != 0:
                logger.info("Creating mongodb user...")
                self._run_command(["sudo", "useradd", "-r", "-s", "/bin/false", "mongodb"])
            
            # Create required directories
            dirs_to_create = [
                "/var/lib/mongodb",
                "/var/log/mongodb",
                "/var/run/mongodb"
            ]
            
            for directory in dirs_to_create:
                if not os.path.exists(directory):
                    logger.info(f"Creating directory: {directory}")
                    self._run_command(["sudo", "mkdir", "-p", directory])
                    self._run_command(["sudo", "chown", "mongodb:mongodb", directory])
                    self._run_command(["sudo", "chmod", "755", directory])
            
            # Try to restart the service
            logger.info("Attempting to restart MongoDB service...")
            commands = [
                ["sudo", "systemctl", "daemon-reload"],
                ["sudo", "systemctl", "enable", "mongod"],
                ["sudo", "systemctl", "restart", "mongod"]
            ]
            
            for cmd in commands:
                code, output = self._run_command(cmd)
                if code != 0:
                    logger.error(f"Failed to run '{' '.join(cmd)}': {output}")
            
            # Final status check
            code, final_status = self._run_command(["systemctl", "is-active", "mongod"])
            if code == 0:
                logger.info("MongoDB service is now running!")
                return True
            else:
                logger.error("MongoDB service failed to start after diagnostics")
                return False
            
        except Exception as e:
            logger.error(f"Error during MongoDB diagnostics: {e}")
            return False
    
    def _install_windows_packages(self) -> bool:
        """Install required packages on Windows."""
        import urllib.request
        import tempfile
        import zipfile
        
        logger.info("Installing Windows packages...")
        packages = {
            "nmap": {
                "url": "https://nmap.org/dist/nmap-7.94-setup.exe",
                "filename": "nmap-setup.exe"
            },
            "mongodb": {
                "url": "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-6.0.13-signed.msi",
                "filename": "mongodb-setup.msi"
            },
            "influxdb": {
                "url": "https://dl.influxdata.com/influxdb/releases/influxdb2-2.7.5-windows-amd64.msi",
                "filename": "influxdb-setup.msi"
            }
        }
        
        success = True
        temp_dir = tempfile.gettempdir()
        
        for package, info in packages.items():
            try:
                logger.info(f"Downloading {package}...")
                file_path = os.path.join(temp_dir, info["filename"])
                
                # Download the installer
                urllib.request.urlretrieve(info["url"], file_path)
                
                # Install the package
                logger.info(f"Installing {package}...")
                if file_path.endswith(".msi"):
                    code, output = self._run_command(["msiexec", "/i", file_path, "/quiet", "/norestart"])
                else:
                    code, output = self._run_command([file_path, "/S"])
                
                if code != 0:
                    logger.error(f"Failed to install {package}: {output}")
                    success = False
                else:
                    logger.info(f"{package} installed successfully")
                
                # Clean up
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                
            except Exception as e:
                logger.error(f"Failed to install {package}: {e}")
                success = False
        
        return success
    
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
            
            # Add MongoDB repository for Debian 12 (Bookworm)
            logger.info("Adding MongoDB repository...")
            try:
                # Import MongoDB public key
                key_cmd = ["curl", "-fsSL", "https://pgp.mongodb.com/server-7.0.asc", "|", "sudo", "gpg", "-o", "/usr/share/keyrings/mongodb-server-7.0.gpg", "--dearmor"]
                code, output = self._run_command(key_cmd)
                if code != 0:
                    logger.error(f"Failed to download MongoDB key: {output}")
                    return False
                
                # Add MongoDB repository with signed-by option
                repo_content = "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main"
                with open("/tmp/mongodb-org-7.0.list", "w") as f:
                    f.write(repo_content)
                
                mv_cmd = ["sudo", "mv", "/tmp/mongodb-org-7.0.list", "/etc/apt/sources.list.d/"]
                code, output = self._run_command(mv_cmd)
                if code != 0:
                    logger.error(f"Failed to add MongoDB repository: {output}")
                    return False
                
                # Update package list
                code, _ = self._run_command(["sudo", "apt", "update"])
                if code != 0:
                    logger.error("Failed to update package list after adding MongoDB repository")
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
            
            # After installing MongoDB, run diagnostics
            if not self._run_mongodb_diagnostics():
                logger.warning("MongoDB installation completed but service diagnostics failed")
                logger.info("Please check the logs above for detailed diagnostic information")
            
            return True
        
        elif self.os_type == "windows":
            return self._install_windows_packages()
        
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
        """Create necessary directories with proper permissions."""
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
        
        if self.os_type == "linux":
            # Use sudo to create and set permissions for Linux directories
            for directory in directories["linux"]:
                try:
                    # Create directory with sudo
                    code, output = self._run_command(["sudo", "mkdir", "-p", directory])
                    if code != 0:
                        logger.error(f"Failed to create directory {directory}: {output}")
                        return False
                    
                    # Get the current user
                    code, user_output = self._run_command(["whoami"])
                    if code != 0:
                        logger.error("Failed to get current user")
                        return False
                    current_user = user_output.strip()
                    
                    # Set ownership to current user
                    code, output = self._run_command(["sudo", "chown", f"{current_user}:{current_user}", directory])
                    if code != 0:
                        logger.error(f"Failed to set ownership for {directory}: {output}")
                        return False
                    
                    # Set permissions (755 - user can read/write, others can read/execute)
                    code, output = self._run_command(["sudo", "chmod", "755", directory])
                    if code != 0:
                        logger.error(f"Failed to set permissions for {directory}: {output}")
                        return False
                    
                    logger.info(f"Created directory with proper permissions: {directory}")
                except Exception as e:
                    logger.error(f"Failed to setup directory {directory}: {e}")
                    return False
        else:
            # Windows directory creation
            for directory in directories["windows"]:
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
                    # Try both service names (e.g., mongodb and mongod)
                    service_names = []
                    if service == "mongodb":
                        service_names = ["mongodb", "mongod"]
                    elif service == "influxdb":
                        service_names = ["influxdb", "influxdb2"]
                    else:
                        service_names = [service]
                    
                    success = False
                    error_messages = []
                    
                    for service_name in service_names:
                        try:
                            # Check if service exists
                            code, output = self._run_command(["systemctl", "list-unit-files", f"{service_name}.service"])
                            if code != 0 or f"{service_name}.service" not in output:
                                error_messages.append(f"Service {service_name} not found")
                                continue
                            
                            # Check service status for more detailed information
                            code, status = self._run_command(["systemctl", "status", service_name])
                            if "not-found" in (status or ""):
                                error_messages.append(f"Service {service_name} not found")
                                continue
                            
                            commands = [
                                ["sudo", "systemctl", "daemon-reload"],
                                ["sudo", "systemctl", "enable", service_name],
                                ["sudo", "systemctl", "start", service_name]
                            ]
                            
                            service_started = True
                            for cmd in commands:
                                code, output = self._run_command(cmd)
                                if code != 0:
                                    error_messages.append(f"Failed to run '{' '.join(cmd)}': {output}")
                                    service_started = False
                                    break
                            
                            if service_started:
                                # Verify service is actually running
                                code, status = self._run_command(["systemctl", "is-active", service_name])
                                if code == 0:
                                    logger.info(f"Service {service_name} started successfully")
                                    success = True
                                    break
                                else:
                                    error_messages.append(f"Service {service_name} failed to start properly")
                            
                        except Exception as e:
                            error_messages.append(f"Error starting {service_name}: {str(e)}")
                    
                    if not success:
                        # Log all collected error messages
                        for error in error_messages:
                            logger.error(error)
                        
                        # Try to get more diagnostic information
                        try:
                            # Check system logs for service errors
                            code, logs = self._run_command(["journalctl", "-u", service_names[0], "-n", "10"])
                            if code == 0 and logs:
                                logger.error(f"Recent service logs:\n{logs}")
                            
                            # Check if MongoDB data directory exists and has correct permissions
                            if service == "mongodb":
                                data_dirs = ["/var/lib/mongodb", "/var/lib/mongo"]
                                for data_dir in data_dirs:
                                    if os.path.exists(data_dir):
                                        code, output = self._run_command(["ls", "-l", data_dir])
                                        if code == 0:
                                            logger.info(f"MongoDB data directory permissions:\n{output}")
                                        
                                        # Fix permissions if needed
                                        code, _ = self._run_command(["sudo", "chown", "-R", "mongodb:mongodb", data_dir])
                                        code, _ = self._run_command(["sudo", "chmod", "-R", "755", data_dir])
                                        
                                        # Try starting the service again
                                        code, _ = self._run_command(["sudo", "systemctl", "start", service_names[0]])
                                        if code == 0:
                                            logger.info(f"Service {service_names[0]} started after fixing permissions")
                                            success = True
                                            break
                        except Exception as e:
                            logger.error(f"Error during diagnostics: {str(e)}")
                        
                        if not success:
                            return False
                
                elif self.os_type == "windows":
                    # Map service names to Windows service names
                    service_map = {
                        "mongodb": "MongoDB",
                        "influxdb": "influxdb",
                        "unbound": "unbound"
                    }
                    
                    service_name = service_map.get(service, service)
                    
                    # Try to enable and start the service
                    try:
                        # Enable the service
                        code, output = self._run_command(["sc", "config", service_name, "start=", "auto"])
                        if code != 0:
                            logger.error(f"Failed to configure {service} service: {output}")
                            return False
                        
                        # Start the service
                        code, output = self._run_command(["net", "start", service_name])
                        if code != 0:
                            logger.error(f"Failed to start {service} service: {output}")
                            
                            # Check if service exists
                            code, status = self._run_command(["sc", "query", service_name])
                            if code != 0:
                                logger.error(f"Service {service} is not installed properly")
                                
                                # Try to fix MongoDB service
                                if service == "mongodb":
                                    logger.info("Attempting to fix MongoDB service...")
                                    mongo_cmd = [
                                        "mongod",
                                        "--install",
                                        "--serviceName", "MongoDB",
                                        "--serviceDisplayName", "MongoDB",
                                        "--dbpath", "C:\\data\\db",
                                        "--logpath", "C:\\data\\log\\mongodb.log",
                                        "--directoryperdb"
                                    ]
                                    
                                    # Create directories
                                    os.makedirs("C:\\data\\db", exist_ok=True)
                                    os.makedirs("C:\\data\\log", exist_ok=True)
                                    
                                    code, output = self._run_command(mongo_cmd)
                                    if code != 0:
                                        logger.error(f"Failed to install MongoDB service: {output}")
                                        return False
                                    
                                    # Try starting the service again
                                    code, output = self._run_command(["net", "start", "MongoDB"])
                                    if code != 0:
                                        logger.error(f"Failed to start MongoDB service after installation: {output}")
                                        return False
                                
                                # Try to fix InfluxDB service
                                elif service == "influxdb":
                                    logger.info("Attempting to fix InfluxDB service...")
                                    influx_cmd = [
                                        "influxd",
                                        "--service", "install"
                                    ]
                                    
                                    code, output = self._run_command(influx_cmd)
                                    if code != 0:
                                        logger.error(f"Failed to install InfluxDB service: {output}")
                                        return False
                                    
                                    # Try starting the service again
                                    code, output = self._run_command(["net", "start", "influxdb"])
                                    if code != 0:
                                        logger.error(f"Failed to start InfluxDB service after installation: {output}")
                                        return False
                            
                            return False
                        
                    except Exception as e:
                        logger.error(f"Error managing {service} service: {e}")
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
            
            # Check if git is installed
            code, _ = self._run_command(["git", "--version"])
            if code != 0:
                logger.error("Git is not installed. Installing git...")
                if self.os_type == "linux":
                    code, output = self._run_command(["sudo", "apt", "install", "-y", "git"])
                    if code != 0:
                        logger.error(f"Failed to install git: {output}")
                        return False
                else:
                    logger.error("Please install git manually on Windows")
                    return False
            
            # Check if git is initialized
            if not (self.base_dir / ".git").exists():
                logger.info("Initializing git repository...")
                code, output = self._run_command(["git", "init"])
                if code != 0:
                    logger.error(f"Failed to initialize git repository: {output}")
                    return False
            
            # Configure git if not already configured
            code, name_output = self._run_command(["git", "config", "--get", "user.name"])
            code2, email_output = self._run_command(["git", "config", "--get", "user.email"])
            
            if code != 0 or not name_output.strip():
                # Try to get system username first
                code, sys_user = self._run_command(["whoami"])
                git_user = "nobody9711" if code != 0 else sys_user.strip()
                code, _ = self._run_command(["git", "config", "--global", "user.name", git_user])
                if code != 0:
                    logger.error("Failed to configure git username")
                    return False
            
            if code2 != 0 or not email_output.strip():
                git_email = f"{name_output.strip() if name_output else 'user'}@{platform.node()}"
                code, _ = self._run_command(["git", "config", "--global", "user.email", git_email])
                if code != 0:
                    logger.error("Failed to configure git email")
                    return False
            
            # Check if remote exists and is correct
            code, remote_output = self._run_command(["git", "remote", "-v"])
            if code != 0 or "origin" not in (remote_output or ""):
                # Remove existing origin if it exists but is wrong
                if "origin" in (remote_output or ""):
                    code, _ = self._run_command(["git", "remote", "remove", "origin"])
                
                logger.info("Adding GitHub remote...")
                code, output = self._run_command(["git", "remote", "add", "origin", self.github_repo])
                if code != 0:
                    logger.error(f"Failed to add GitHub remote: {output}")
                    return False
            elif self.github_repo not in (remote_output or ""):
                # Update remote URL if it's different
                code, output = self._run_command(["git", "remote", "set-url", "origin", self.github_repo])
                if code != 0:
                    logger.error(f"Failed to update remote URL: {output}")
                    return False
            
            # Ensure we're on the correct branch
            code, branch_output = self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            current_branch = branch_output.strip() if code == 0 else ""
            
            if current_branch != self.github_branch:
                code, _ = self._run_command(["git", "checkout", "-B", self.github_branch])
                if code != 0:
                    logger.error(f"Failed to switch to {self.github_branch} branch")
                    return False
            
            # Add all changes
            logger.info("Adding changes...")
            code, output = self._run_command(["git", "add", "."])
            if code != 0:
                logger.error(f"Failed to add changes: {output}")
                return False
            
            # Get status to check for changes
            code, status_output = self._run_command(["git", "status", "--porcelain"])
            if status_output.strip():
                # Changes exist, commit them
                logger.info("Committing changes...")
                commit_msg = "Update from setup script: " + ", ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Update from setup script"
                code, output = self._run_command(["git", "commit", "-m", commit_msg])
                if code != 0:
                    logger.error(f"Failed to commit changes: {output}")
                    return False
                
                # Pull latest changes first to avoid conflicts
                logger.info("Pulling latest changes...")
                code, output = self._run_command(["git", "pull", "--rebase", "origin", self.github_branch])
                if code != 0:
                    logger.warning(f"Failed to pull latest changes: {output}")
                    # Continue anyway, as this might be the first push
                
                # Push changes
                logger.info("Pushing changes to GitHub...")
                code, output = self._run_command(["git", "push", "-u", "origin", self.github_branch])
                if code != 0:
                    logger.error(f"Failed to push changes: {output}")
                    return False
                
                logger.info("Changes pushed to GitHub successfully!")
            else:
                logger.info("No changes to commit")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update GitHub repository: {e}")
            return False
    
    def check_all_requirements(self) -> Dict[str, bool]:
        """Check all requirements and dependencies."""
        requirements = {
            "python_version": False,
            "system_packages": False,
            "python_packages": False,
            "directories": False,
            "services": {
                "mongodb": False,
                "influxdb": False,
                "unbound": False
            },
            "config": False,
            "permissions": False,
            "network": False
        }
        
        try:
            # Check Python version
            requirements["python_version"] = self.check_python_version()
            logger.info(f"Python version check: {'✓' if requirements['python_version'] else '✗'}")
            
            # Check system packages
            missing_packages = self.check_system_packages()
            requirements["system_packages"] = len(missing_packages) == 0
            if missing_packages:
                logger.info(f"Missing system packages: {', '.join(missing_packages)}")
            else:
                logger.info("System packages check: ✓")
            
            # Check Python packages
            venv_path = self.base_dir / "venv"
            if venv_path.exists():
                if self.os_type == "windows":
                    pip_path = venv_path / "Scripts" / "pip.exe"
                else:
                    pip_path = venv_path / "bin" / "pip"
                
                code, output = self._run_command([str(pip_path), "freeze"])
                installed_packages = {p.split('==')[0].lower() for p in output.split('\n') if p}
                missing_py_packages = [p for p in self.python_packages if p.lower() not in installed_packages]
                requirements["python_packages"] = len(missing_py_packages) == 0
                if missing_py_packages:
                    logger.info(f"Missing Python packages: {', '.join(missing_py_packages)}")
                else:
                    logger.info("Python packages check: ✓")
            
            # Check directories
            directories = {
                "linux": [
                    "/var/log/network-monitor",
                    "/tmp/network-monitor",
                    "/var/lib/mongodb",
                    "/var/log/mongodb",
                    "/var/run/mongodb"
                ],
                "windows": [
                    os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\logs"),
                    os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\temp")
                ]
            }
            
            all_dirs_exist = True
            for directory in directories[self.os_type]:
                if not os.path.exists(directory):
                    logger.info(f"Missing directory: {directory}")
                    all_dirs_exist = False
            requirements["directories"] = all_dirs_exist
            if all_dirs_exist:
                logger.info("Directories check: ✓")
            
            # Check services
            service_status = self.check_services()
            requirements["services"].update(service_status)
            for service, running in service_status.items():
                logger.info(f"Service {service}: {'✓' if running else '✗'}")
            
            # Check configuration
            config_path = self.base_dir / "config.yml"
            requirements["config"] = config_path.exists()
            logger.info(f"Configuration file check: {'✓' if requirements['config'] else '✗'}")
            
            # Check permissions
            if self.os_type == "linux":
                try:
                    # Check if user has sudo access
                    code, _ = self._run_command(["sudo", "-n", "true"])
                    requirements["permissions"] = code == 0
                    logger.info(f"Permissions check: {'✓' if requirements['permissions'] else '✗'}")
                except Exception:
                    requirements["permissions"] = False
                    logger.info("Permissions check: ✗")
            else:
                # On Windows, check if running as administrator
                try:
                    import ctypes
                    requirements["permissions"] = ctypes.windll.shell32.IsUserAnAdmin() != 0
                    logger.info(f"Administrator privileges check: {'✓' if requirements['permissions'] else '✗'}")
                except Exception:
                    requirements["permissions"] = False
                    logger.info("Administrator privileges check: ✗")
            
            # Check network connectivity
            try:
                import socket
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                requirements["network"] = True
                logger.info("Network connectivity check: ✓")
            except Exception:
                requirements["network"] = False
                logger.info("Network connectivity check: ✗")
            
            return requirements
            
        except Exception as e:
            logger.error(f"Error checking requirements: {e}")
            return requirements
    
    def run_setup(self) -> bool:
        """Run the complete setup process."""
        logger.info("Starting Network Monitor setup...")
        
        # Check all requirements first
        requirements = self.check_all_requirements()
        
        # Determine if setup is needed
        setup_needed = not all([
            requirements["python_version"],
            requirements["system_packages"],
            requirements["python_packages"],
            requirements["directories"],
            requirements["config"],
            requirements["permissions"],
            requirements["network"],
            all(requirements["services"].values())
        ])
        
        if setup_needed:
            logger.info("Some requirements are missing. Starting installation...")
            
            if not requirements["permissions"]:
                if self.os_type == "linux":
                    logger.error("Please run this script with sudo privileges")
                else:
                    logger.error("Please run this script as administrator")
                return False
            
            if not requirements["network"]:
                logger.error("No network connectivity. Please check your internet connection")
                return False
            
            if not requirements["python_version"]:
                logger.error("Python version requirement not met")
                return False
            
            success = (
                self.install_system_packages(self.check_system_packages())
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
                
                # Verify all requirements again
                final_requirements = self.check_all_requirements()
                if not all([
                    final_requirements["python_version"],
                    final_requirements["system_packages"],
                    final_requirements["python_packages"],
                    final_requirements["directories"],
                    final_requirements["config"],
                    final_requirements["permissions"],
                    final_requirements["network"],
                    all(final_requirements["services"].values())
                ]):
                    logger.warning("Some requirements are still not met after setup")
                    return False
                
                return True
            else:
                logger.error("Setup failed")
                return False
        else:
            logger.info("All requirements are met!")
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