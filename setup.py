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
            "services": False,
            "config": False,
            "permissions": False
        }
        
        try:
            # Check Python version
            logger.info("Checking Python version...")
            requirements["python_version"] = self.check_python_version()
            
            # Check system packages
            logger.info("Checking system packages...")
            missing_packages = self.check_system_packages()
            requirements["system_packages"] = len(missing_packages) == 0
            if missing_packages:
                logger.warning(f"Missing system packages: {', '.join(missing_packages)}")
            
            # Check Python packages
            logger.info("Checking Python packages...")
            if os.path.exists(self.base_dir / "venv"):
                venv_pip = str(self.base_dir / "venv" / ("Scripts" if self.os_type == "windows" else "bin") / "pip")
                code, output = self._run_command([venv_pip, "freeze"])
                installed_packages = {p.split("==")[0].lower() for p in output.split("\n") if p}
                missing_py_packages = [p for p in self.python_packages if p.lower() not in installed_packages]
                requirements["python_packages"] = len(missing_py_packages) == 0
                if missing_py_packages:
                    logger.warning(f"Missing Python packages: {', '.join(missing_py_packages)}")
            
            # Check directories
            logger.info("Checking required directories...")
            directories = {
                "linux": ["/var/log/network-monitor", "/tmp/network-monitor"],
                "windows": [
                    os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\logs"),
                    os.path.expandvars("%PROGRAMDATA%\\NetworkMonitor\\temp")
                ]
            }
            
            all_dirs_exist = True
            for directory in directories[self.os_type]:
                if not os.path.exists(directory):
                    all_dirs_exist = False
                    logger.warning(f"Missing directory: {directory}")
            requirements["directories"] = all_dirs_exist
            
            # Check services
            logger.info("Checking required services...")
            services = self.check_services()
            requirements["services"] = all(services.values())
            if not all(services.values()):
                inactive_services = [s for s, running in services.items() if not running]
                logger.warning(f"Inactive services: {', '.join(inactive_services)}")
            
            # Check configuration
            logger.info("Checking configuration...")
            config_exists = (self.base_dir / "config.yml").exists()
            requirements["config"] = config_exists
            if not config_exists:
                logger.warning("Missing configuration file: config.yml")
            
            # Check permissions
            logger.info("Checking permissions...")
            if self.os_type == "linux":
                # Check data directories permissions
                data_dirs = ["/var/lib/mongodb", "/var/lib/mongo", "/var/log/mongodb"]
                permissions_ok = True
                for directory in data_dirs:
                    if os.path.exists(directory):
                        code, owner = self._run_command(["stat", "-c", "%U:%G", directory])
                        if code == 0 and "mongodb:mongodb" not in owner.strip():
                            permissions_ok = False
                            logger.warning(f"Incorrect permissions on {directory}: {owner.strip()}")
                requirements["permissions"] = permissions_ok
            else:
                requirements["permissions"] = True  # Windows handles permissions differently
            
            return requirements
            
        except Exception as e:
            logger.error(f"Error checking requirements: {e}")
            return requirements
    
    def fix_requirements(self, requirements: Dict[str, bool]) -> bool:
        """Fix any missing or incorrect requirements."""
        try:
            if not requirements["python_version"]:
                logger.error("Python version requirement cannot be fixed automatically")
                return False
            
            if not requirements["system_packages"]:
                logger.info("Installing missing system packages...")
                if not self.install_system_packages(self.check_system_packages()):
                    return False
            
            if not requirements["python_packages"]:
                logger.info("Setting up Python environment...")
                if not self.setup_virtual_environment():
                    return False
                if not self.install_python_packages():
                    return False
            
            if not requirements["directories"]:
                logger.info("Creating required directories...")
                if not self.setup_directories():
                    return False
            
            if not requirements["services"]:
                logger.info("Starting required services...")
                if not self.start_services(self.check_services()):
                    return False
            
            if not requirements["config"]:
                logger.info("Creating configuration file...")
                if not self.create_config():
                    return False
            
            if not requirements["permissions"]:
                logger.info("Fixing permissions...")
                if self.os_type == "linux":
                    if not self._run_mongodb_diagnostics():
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error fixing requirements: {e}")
            return False
    
    def run_setup(self) -> bool:
        """Run the complete setup process."""
        logger.info("Starting Network Monitor setup...")
        
        # Check all requirements first
        requirements = self.check_all_requirements()
        
        # If any requirements are not met, try to fix them
        if not all(requirements.values()):
            logger.info("Some requirements are not met. Attempting to fix...")
            if not self.fix_requirements(requirements):
                logger.error("Failed to fix all requirements")
                return False
            
            # Check requirements again after fixing
            requirements = self.check_all_requirements()
            if not all(requirements.values()):
                logger.error("Some requirements are still not met after attempting fixes")
                return False
        
        logger.info("All requirements are met!")
        
        # Update GitHub repository
        if not self.update_github():
            logger.warning("Setup completed but failed to update GitHub repository")
        
        return True

def main():
    setup = SetupManager()
    if setup.run_setup():
        logger.info("""
Network Monitor setup completed successfully!

To start the application:
1. Edit config.yml with your specific settings (if you haven't already)
2. Activate the virtual environment:
   - Windows: .\\venv\\Scripts\\activate
   - Linux: source venv/bin/activate
3. Run the application:
   python src/main.py

For more information, please refer to the README.md file.
""")
        
        # Try to start the application automatically
        try:
            venv_python = str(setup.base_dir / "venv" / ("Scripts" if setup.os_type == "windows" else "bin") / "python")
            if os.path.exists(setup.base_dir / "src" / "main.py"):
                logger.info("Starting the application...")
                subprocess.Popen([venv_python, "src/main.py"])
            else:
                logger.error("Could not find src/main.py to start the application")
        except Exception as e:
            logger.error(f"Failed to start the application: {e}")
        
        sys.exit(0)
    else:
        logger.error("Setup failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 