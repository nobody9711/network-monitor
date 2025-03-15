#!/usr/bin/env python3
"""
Network Monitor - Main Application Entry Point
A comprehensive network monitoring tool for Raspberry Pi with Pi-hole and Unbound
"""

import os
import sys
import time
import logging
import argparse
import threading
from pathlib import Path

# Add the parent directory to sys.path to allow importing project modules
sys.path.append(str(Path(__file__).parent.parent))

from src.core.config import load_config, Config
from src.core.manager import NetworkMonitorManager
from src.api.server import start_api_server
from src.dashboard.app import start_dashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("network_monitor.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Network Monitor')
    parser.add_argument('--config', type=str, default='.env',
                        help='Path to configuration file')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--no-dashboard', action='store_true',
                        help='Run without the web dashboard')
    parser.add_argument('--no-api', action='store_true',
                        help='Run without the API server')
    return parser.parse_args()

def main():
    """Main application entry point."""
    args = parse_args()
    
    # Set up logger level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Load configuration
    config = load_config(args.config)
    
    # Initialize the network monitor manager
    manager = NetworkMonitorManager(config)
    
    # Start data collection in a separate thread
    collector_thread = threading.Thread(
        target=manager.start,
        daemon=True
    )
    collector_thread.start()
    logger.info("Network data collection started")
    
    # Start API server if enabled
    api_thread = None
    if not args.no_api:
        api_thread = threading.Thread(
            target=start_api_server,
            args=(manager, config),
            daemon=True
        )
        api_thread.start()
        logger.info(f"API server started on http://{config.api_host}:{config.api_port}")
    
    # Start dashboard if enabled
    dashboard_thread = None
    if not args.no_dashboard:
        dashboard_thread = threading.Thread(
            target=start_dashboard,
            args=(manager, config),
            daemon=True
        )
        dashboard_thread.start()
        logger.info(f"Dashboard started on http://{config.dashboard_host}:{config.dashboard_port}")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Network Monitor...")
        manager.stop()
        logger.info("Network Monitor has been shut down")
        sys.exit(0)

if __name__ == "__main__":
    main() 