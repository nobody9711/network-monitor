#!/bin/bash

# Network Monitor Setup Script Wrapper

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run this script with sudo:"
    echo "sudo ./setup.sh"
    exit 1
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Installing..."
    apt update
    apt install -y python3
fi

# Make setup.py executable
chmod +x setup.py

# Run setup script
python3 setup.py

# Check if setup was successful
if [ $? -eq 0 ]; then
    echo "Setup completed successfully!"
    echo "You can now start the Network Monitor."
else
    echo "Setup failed. Please check the error messages above."
    exit 1
fi 