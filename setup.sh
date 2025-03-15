#!/bin/bash

# Network Monitor Setup Script Wrapper

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run this script with sudo:"
    echo "sudo ./setup.sh"
    exit 1
fi

# Ensure script has execute permissions
chmod +x "$(dirname "$0")/setup.py"

# Create necessary directories with proper permissions
mkdir -p /var/log/network-monitor
chown -R $SUDO_USER:$SUDO_USER /var/log/network-monitor

mkdir -p /tmp/network-monitor
chown -R $SUDO_USER:$SUDO_USER /tmp/network-monitor

# Ensure apt can handle HTTPS repositories
apt update
apt install -y apt-transport-https ca-certificates curl gnupg

# Run setup script
python3 setup.py

# Check if setup was successful
if [ $? -eq 0 ]; then
    echo "Setup completed successfully!"
    echo "You can now start the Network Monitor."
    
    # Set correct ownership for the virtual environment
    if [ -d "venv" ]; then
        chown -R $SUDO_USER:$SUDO_USER venv
    fi
    
    # Set correct ownership for the config file
    if [ -f "config.yml" ]; then
        chown $SUDO_USER:$SUDO_USER config.yml
    fi
else
    echo "Setup failed. Please check the error messages above."
    exit 1
fi 