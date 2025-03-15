"""
Windows Network Collector
Collects network interface statistics and device information for Windows systems
"""

import psutil
import logging
import wmi
import time
import socket
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
import winreg
import netifaces
import nmap

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage
from src.database.mongo import MongoDBStorage

logger = logging.getLogger(__name__)

class NetworkCollector(BaseCollector):
    """Collects network metrics and device information for Windows systems."""
    
    def __init__(self, influx_db: InfluxDBStorage, mongo_db: MongoDBStorage,
                collection_interval: int = 30):
        """
        Initialize the network collector.
        
        Args:
            influx_db: InfluxDB storage instance
            mongo_db: MongoDB storage instance
            collection_interval: How often to collect metrics (seconds)
        """
        super().__init__(collection_interval)
        self.influx_db = influx_db
        self.mongo_db = mongo_db
        self.wmi_client = None
        self.nm = nmap.PortScanner()
        
        try:
            self.wmi_client = wmi.WMI()
            logger.info("WMI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WMI client: {e}")
        
        # Get local network information
        self.local_ip = self._get_local_ip()
        self.network_prefix = self._get_network_prefix()
        
        logger.info(f"Network collector initialized. Local IP: {self.local_ip}")
    
    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            # Create a temporary socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Connect to Google DNS
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            logger.error(f"Error getting local IP: {e}")
            return "127.0.0.1"
    
    def _get_network_prefix(self) -> str:
        """Get the network prefix for scanning."""
        try:
            # Get the first three octets of the local IP
            prefix = ".".join(self.local_ip.split(".")[:3])
            return f"{prefix}.0/24"
        except Exception as e:
            logger.error(f"Error getting network prefix: {e}")
            return "192.168.1.0/24"
    
    def _get_interface_info(self) -> List[Dict[str, Any]]:
        """Get information about network interfaces."""
        interfaces = []
        try:
            # Get network interfaces using WMI
            if self.wmi_client:
                network_adapters = self.wmi_client.Win32_NetworkAdapter(
                    PhysicalAdapter=True
                )
                
                for adapter in network_adapters:
                    try:
                        # Get adapter configuration
                        adapter_config = self.wmi_client.Win32_NetworkAdapterConfiguration(
                            Index=adapter.Index
                        )[0]
                        
                        interface = {
                            "name": adapter.Name,
                            "description": adapter.Description,
                            "mac_address": adapter.MACAddress,
                            "adapter_type": adapter.AdapterType,
                            "speed": adapter.Speed,
                            "status": adapter.Status,
                            "ip_addresses": adapter_config.IPAddress or [],
                            "subnet_masks": adapter_config.IPSubnet or [],
                            "default_gateway": adapter_config.DefaultIPGateway or [],
                            "dns_servers": adapter_config.DNSServerSearchOrder or [],
                            "dhcp_enabled": adapter_config.DHCPEnabled,
                            "dhcp_server": adapter_config.DHCPServer
                        }
                        
                        interfaces.append(interface)
                    except Exception as e:
                        logger.warning(f"Error getting interface config: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error getting network interfaces: {e}")
        
        return interfaces
    
    def _get_network_usage(self) -> Dict[str, Any]:
        """Get network usage statistics."""
        try:
            # Get network I/O counters
            net_io = psutil.net_io_counters(pernic=True)
            
            # Process each interface
            interface_stats = {}
            for interface, stats in net_io.items():
                interface_stats[interface] = {
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "packets_sent": stats.packets_sent,
                    "packets_recv": stats.packets_recv,
                    "errin": stats.errin,
                    "errout": stats.errout,
                    "dropin": stats.dropin,
                    "dropout": stats.dropout
                }
            
            return interface_stats
        except Exception as e:
            logger.error(f"Error getting network usage: {e}")
            return {}
    
    def _scan_network(self) -> List[Dict[str, Any]]:
        """Scan the network for devices."""
        devices = []
        try:
            # Perform a quick ping scan
            self.nm.scan(hosts=self.network_prefix, arguments="-sn")
            
            # Process discovered hosts
            for host in self.nm.all_hosts():
                try:
                    # Get host information
                    hostname = socket.getfqdn(host)
                    mac_address = None
                    vendor = None
                    
                    # Try to get MAC address using ARP
                    try:
                        result = subprocess.run(
                            ["arp", "-a", host],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            # Parse ARP output to get MAC address
                            lines = result.stdout.split("\n")
                            for line in lines:
                                if host in line:
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        mac_address = parts[1].strip()
                                        break
                    except Exception as e:
                        logger.debug(f"Error getting MAC address for {host}: {e}")
                    
                    # Get vendor information if we have a MAC address
                    if mac_address:
                        try:
                            # Query WMI for vendor information
                            if self.wmi_client:
                                adapters = self.wmi_client.Win32_NetworkAdapter(
                                    MACAddress=mac_address
                                )
                                if adapters:
                                    vendor = adapters[0].Manufacturer
                        except Exception as e:
                            logger.debug(f"Error getting vendor for {mac_address}: {e}")
                    
                    device = {
                        "ip": host,
                        "hostname": hostname,
                        "mac": mac_address,
                        "vendor": vendor,
                        "last_seen": datetime.now().isoformat(),
                        "status": "active"
                    }
                    
                    devices.append(device)
                except Exception as e:
                    logger.warning(f"Error processing host {host}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error scanning network: {e}")
        
        return devices
    
    def collect(self) -> Dict[str, Any]:
        """Collect network metrics and device information."""
        try:
            # Get interface information
            interfaces = self._get_interface_info()
            
            # Get network usage statistics
            network_usage = self._get_network_usage()
            
            # Scan for devices
            devices = self._scan_network()
            
            # Update device information in MongoDB
            self._update_devices(devices)
            
            # Prepare metrics for InfluxDB
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "interfaces": interfaces,
                "network_usage": network_usage,
                "active_devices": len(devices)
            }
            
            # Store metrics
            self.store_data(metrics)
            
            return metrics
        except Exception as e:
            logger.error(f"Error collecting network data: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _update_devices(self, devices: List[Dict[str, Any]]) -> None:
        """Update device information in MongoDB."""
        try:
            # Get existing devices
            existing_devices = self.mongo_db.get_all_devices()
            existing_macs = {d["mac"]: d for d in existing_devices if "mac" in d}
            
            # Update or insert devices
            for device in devices:
                if not device.get("mac"):
                    continue
                
                if device["mac"] in existing_macs:
                    # Update existing device
                    existing = existing_macs[device["mac"]]
                    updates = {
                        "last_seen": device["last_seen"],
                        "status": "active"
                    }
                    
                    # Update IP if changed
                    if device["ip"] != existing.get("ip"):
                        updates["ip"] = device["ip"]
                    
                    # Update hostname if we have a better one
                    if device["hostname"] != "localhost" and device["hostname"] != device["ip"]:
                        updates["hostname"] = device["hostname"]
                    
                    self.mongo_db.update_device(device["mac"], updates)
                else:
                    # Insert new device
                    self.mongo_db.create_device(device)
            
            # Mark devices not seen recently as inactive
            one_hour_ago = (
                datetime.now() - datetime.timedelta(hours=1)
            ).isoformat()
            
            self.mongo_db.update_devices_status(
                {"last_seen": {"$lt": one_hour_ago}},
                "inactive"
            )
        except Exception as e:
            logger.error(f"Error updating devices: {e}")
    
    def store_data(self, metrics: Dict[str, Any]) -> None:
        """Store network metrics in InfluxDB."""
        try:
            # Format metrics for InfluxDB
            data_points = []
            
            # Add interface metrics
            for interface in metrics.get("interfaces", []):
                if interface.get("name") and interface.get("speed"):
                    data_points.append({
                        "measurement": "network_interface",
                        "time": metrics["timestamp"],
                        "tags": {
                            "interface": interface["name"]
                        },
                        "fields": {
                            "speed": float(interface["speed"]) if interface["speed"] else 0,
                            "status": 1 if interface["status"] == "Up" else 0
                        }
                    })
            
            # Add network usage metrics
            for interface, stats in metrics.get("network_usage", {}).items():
                data_points.append({
                    "measurement": "network_usage",
                    "time": metrics["timestamp"],
                    "tags": {
                        "interface": interface
                    },
                    "fields": {
                        "bytes_sent": stats["bytes_sent"],
                        "bytes_recv": stats["bytes_recv"],
                        "packets_sent": stats["packets_sent"],
                        "packets_recv": stats["packets_recv"],
                        "errin": stats["errin"],
                        "errout": stats["errout"],
                        "dropin": stats["dropin"],
                        "dropout": stats["dropout"]
                    }
                })
            
            # Add active devices count
            data_points.append({
                "measurement": "network_devices",
                "time": metrics["timestamp"],
                "fields": {
                    "active_devices": metrics.get("active_devices", 0)
                }
            })
            
            # Store in InfluxDB
            self.influx_db.write_points(data_points)
            logger.debug("Network metrics stored successfully")
        except Exception as e:
            logger.error(f"Error storing network metrics: {e}", exc_info=True) 