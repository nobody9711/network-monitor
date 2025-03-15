#!/bin/bash

# Set script to exit on error
set -e

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "Please run this script with sudo:"
        echo "sudo ./start.sh"
        exit 1
    fi
}

# Function to check and start a service
check_service() {
    local service_name="$1"
    if ! systemctl is-active --quiet "$service_name"; then
        echo "Starting $service_name service..."
        systemctl start "$service_name" || {
            echo "Failed to start $service_name service"
            return 1
        }
    fi
}

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
CONFIG_FILE="$SCRIPT_DIR/config.yml"
SETUP_SCRIPT="$SCRIPT_DIR/setup.py"

# Check root privileges
check_root

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Running setup script..."
    python3 "$SETUP_SCRIPT" || {
        echo "Setup failed. Please check the error messages above."
        exit 1
    }
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file not found. Running setup script..."
    python3 "$SETUP_SCRIPT" || {
        echo "Setup failed. Please check the error messages above."
        exit 1
    }
fi

# Check and start required services
echo "Checking required services..."
services=("mongodb" "mongod" "influxdb" "unbound")
for service in "${services[@]}"; do
    if systemctl list-unit-files "$service.service" &>/dev/null; then
        check_service "$service" || true
    fi
done

# Activate virtual environment
source "$VENV_DIR/bin/activate" || {
    echo "Failed to activate virtual environment"
    exit 1
}

# Run the application
echo "Starting Network Monitor..."
cd "$SCRIPT_DIR"
python src/main.py

# Deactivate virtual environment on exit
deactivate 