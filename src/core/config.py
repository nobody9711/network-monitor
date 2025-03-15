"""
Configuration module for Network Monitor.
Handles loading settings from environment variables or config files.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration settings for Network Monitor."""
    # Network interface to monitor
    network_interface: str
    
    # MongoDB connection
    mongodb_uri: str
    mongodb_db: str
    
    # InfluxDB connection
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str
    
    # API settings
    api_host: str
    api_port: int
    
    # Dashboard settings
    dashboard_host: str
    dashboard_port: int
    
    # Pi-hole settings
    pihole_enabled: bool
    pihole_api_url: Optional[str]
    pihole_api_key: Optional[str]
    
    # Unbound settings
    unbound_enabled: bool
    unbound_control_path: Optional[str]
    
    # Security settings
    alert_email: Optional[str]
    smtp_server: Optional[str]
    smtp_port: Optional[int]
    smtp_username: Optional[str]
    smtp_password: Optional[str]
    
    # Data collection intervals (in seconds)
    bandwidth_interval: int 
    device_scan_interval: int
    performance_interval: int
    security_scan_interval: int
    
    # Retention periods (in days)
    metrics_retention_days: int
    events_retention_days: int
    
    # Security thresholds
    bandwidth_alert_threshold: float  # MB/s
    cpu_alert_threshold: float  # Percent
    
    # Feature flags
    enable_packet_capture: bool
    enable_security_scanning: bool

def load_config(config_path: str = None) -> Config:
    """
    Load configuration from .env file and environment variables.
    
    Args:
        config_path: Path to .env file (optional)
        
    Returns:
        Config: Configuration object with all settings
    """
    # Load from .env file if provided
    if config_path and Path(config_path).exists():
        load_dotenv(config_path)
    else:
        # Try to load from default locations
        load_dotenv()
    
    # Network interface - try to auto-detect if not specified
    network_interface = os.getenv("NETWORK_INTERFACE", "")
    if not network_interface:
        import netifaces
        # Get the first non-loopback interface that's up
        for iface in netifaces.interfaces():
            if iface != 'lo' and netifaces.AF_INET in netifaces.ifaddresses(iface):
                network_interface = iface
                break
        if not network_interface:
            network_interface = "eth0"  # Default for Raspberry Pi
        logger.info(f"Auto-detected network interface: {network_interface}")
    
    # MongoDB settings
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db = os.getenv("MONGODB_DB", "network_monitor")
    
    # InfluxDB settings
    influxdb_url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    influxdb_token = os.getenv("INFLUXDB_TOKEN", "")
    influxdb_org = os.getenv("INFLUXDB_ORG", "network_monitor")
    influxdb_bucket = os.getenv("INFLUXDB_BUCKET", "network_metrics")
    
    # API settings
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "5000"))
    
    # Dashboard settings
    dashboard_host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "8050"))
    
    # Pi-hole settings
    pihole_enabled = os.getenv("PIHOLE_ENABLED", "true").lower() == "true"
    pihole_api_url = os.getenv("PIHOLE_API_URL", "http://localhost/admin/api.php")
    pihole_api_key = os.getenv("PIHOLE_API_KEY", "")
    
    # Unbound settings
    unbound_enabled = os.getenv("UNBOUND_ENABLED", "true").lower() == "true"
    unbound_control_path = os.getenv("UNBOUND_CONTROL_PATH", "/usr/sbin/unbound-control")
    
    # Security settings
    alert_email = os.getenv("ALERT_EMAIL", "")
    smtp_server = os.getenv("SMTP_SERVER", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    smtp_username = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    
    # Data collection intervals
    bandwidth_interval = int(os.getenv("BANDWIDTH_INTERVAL", "5"))
    device_scan_interval = int(os.getenv("DEVICE_SCAN_INTERVAL", "60"))
    performance_interval = int(os.getenv("PERFORMANCE_INTERVAL", "10"))
    security_scan_interval = int(os.getenv("SECURITY_SCAN_INTERVAL", "300"))
    
    # Retention periods
    metrics_retention_days = int(os.getenv("METRICS_RETENTION_DAYS", "30"))
    events_retention_days = int(os.getenv("EVENTS_RETENTION_DAYS", "90"))
    
    # Security thresholds
    bandwidth_alert_threshold = float(os.getenv("BANDWIDTH_ALERT_THRESHOLD", "50"))
    cpu_alert_threshold = float(os.getenv("CPU_ALERT_THRESHOLD", "90"))
    
    # Feature flags
    enable_packet_capture = os.getenv("ENABLE_PACKET_CAPTURE", "true").lower() == "true"
    enable_security_scanning = os.getenv("ENABLE_SECURITY_SCANNING", "true").lower() == "true"
    
    return Config(
        network_interface=network_interface,
        mongodb_uri=mongodb_uri,
        mongodb_db=mongodb_db,
        influxdb_url=influxdb_url,
        influxdb_token=influxdb_token,
        influxdb_org=influxdb_org,
        influxdb_bucket=influxdb_bucket,
        api_host=api_host,
        api_port=api_port,
        dashboard_host=dashboard_host,
        dashboard_port=dashboard_port,
        pihole_enabled=pihole_enabled,
        pihole_api_url=pihole_api_url,
        pihole_api_key=pihole_api_key,
        unbound_enabled=unbound_enabled,
        unbound_control_path=unbound_control_path,
        alert_email=alert_email,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        bandwidth_interval=bandwidth_interval,
        device_scan_interval=device_scan_interval,
        performance_interval=performance_interval,
        security_scan_interval=security_scan_interval,
        metrics_retention_days=metrics_retention_days,
        events_retention_days=events_retention_days,
        bandwidth_alert_threshold=bandwidth_alert_threshold,
        cpu_alert_threshold=cpu_alert_threshold,
        enable_packet_capture=enable_packet_capture,
        enable_security_scanning=enable_security_scanning,
    ) 