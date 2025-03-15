"""
Device Collector - Discovers and tracks devices on the local network
"""

import time
import logging
import datetime
import ipaddress
import re
import subprocess
from typing import Dict, Any, List, Optional, Set, Tuple

import netifaces
import scapy.all as scapy
from scapy.layers.l2 import ARP, Ether

from src.collectors.base import BaseCollector
from src.database.mongo import MongoDBStorage

logger = logging.getLogger(__name__)

# Device type identification patterns
DEVICE_PATTERNS = {
    "router": [r"router", r"gateway", r"ap", r"access point", r"ubiquiti", r"unifi", r"mikrotik", r"asus", r"netgear"],
    "tv": [r"tv", r"television", r"roku", r"firestick", r"appletv", r"chromecast", r"smarttv", r"android tv"],
    "mobile": [r"iphone", r"android", r"smartphone", r"mobile", r"samsung galaxy", r"pixel", r"oneplus"],
    "computer": [r"pc", r"mac", r"macbook", r"desktop", r"laptop", r"server", r"workstation", r"windows", r"linux"],
    "iot": [r"nest", r"hue", r"echo", r"alexa", r"ring", r"smartthings", r"thermostat", r"doorbell", r"camera", r"sensor"],
    "gaming": [r"playstation", r"xbox", r"nintendo", r"switch", r"ps4", r"ps5", r"gaming"]
}

class DeviceCollector(BaseCollector):
    """
    Collector for network device discovery and tracking.
    
    Discovers devices on the local network, tracks their activity,
    and attempts to identify device types and manufacturers.
    """
    
    def __init__(self, interface: str, mongo_db: MongoDBStorage, interval: int = 60):
        """
        Initialize the device collector.
        
        Args:
            interface: Network interface to use for scanning
            mongo_db: MongoDB storage instance
            interval: Collection interval in seconds
        """
        super().__init__(interval=interval)
        self.interface = interface
        self.mongo_db = mongo_db
        self.known_devices = {}  # Cache of known devices
        
        # Get network information
        self.local_ip, self.network_cidr = self._get_network_info()
        logger.info(f"Network interface: {interface}, Local IP: {self.local_ip}, Network: {self.network_cidr}")
    
    def _get_network_info(self) -> Tuple[str, str]:
        """
        Get the local IP address and network CIDR.
        
        Returns:
            Tuple of (local_ip, network_cidr)
        """
        try:
            # Get interface addresses
            addrs = netifaces.ifaddresses(self.interface)
            
            # Get IPv4 address
            if netifaces.AF_INET in addrs:
                addr_info = addrs[netifaces.AF_INET][0]
                ip = addr_info['addr']
                netmask = addr_info['netmask']
                
                # Convert netmask to CIDR notation
                netmask_bits = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
                network_cidr = f"{ip}/{netmask_bits}"
                
                # Normalize to network address
                network = ipaddress.IPv4Network(network_cidr, strict=False)
                network_cidr = str(network)
                
                return ip, network_cidr
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
        
        # Default values if we couldn't determine
        return "127.0.0.1", "192.168.1.0/24"
    
    def _scan_network_arp(self) -> List[Dict[str, Any]]:
        """
        Scan the network using ARP requests to discover devices.
        
        Returns:
            List of discovered devices
        """
        devices = []
        
        try:
            # Create ARP request packet
            network = self.network_cidr.split('/')[0].rsplit('.', 1)[0] + '.0/24'
            arp_request = scapy.ARP(pdst=network)
            broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = broadcast/arp_request
            
            # Send packet and get responses
            logger.debug(f"Scanning network {network} using ARP")
            result = scapy.srp(packet, timeout=3, verbose=0, iface=self.interface)[0]
            
            # Process responses
            for sent, received in result:
                device = {
                    "ip": received.psrc,
                    "mac": received.hwsrc,
                    "last_seen": datetime.datetime.now().isoformat(),
                    "scan_method": "arp"
                }
                devices.append(device)
            
            logger.debug(f"Discovered {len(devices)} devices using ARP scan")
            return devices
        except Exception as e:
            logger.error(f"Error during ARP scan: {e}")
            return []
    
    def _scan_network_ping(self) -> List[Dict[str, Any]]:
        """
        Scan the network using ping sweep to discover devices.
        
        Returns:
            List of discovered devices
        """
        devices = []
        
        try:
            # Get network address
            network = ipaddress.IPv4Network(self.network_cidr)
            network_addr = network.network_address
            netmask = network.prefixlen
            
            # Determine range to scan based on subnet size
            if netmask >= 24:
                # Small network, scan all hosts
                hosts = list(network.hosts())
            else:
                # Larger network, limit scan to common addresses
                base_network = str(network_addr).rsplit('.', 1)[0]
                hosts = []
                for i in range(1, 255):
                    hosts.append(ipaddress.IPv4Address(f"{base_network}.{i}"))
            
            logger.debug(f"Scanning {len(hosts)} hosts using ping sweep")
            
            # Use ping to discover devices
            alive_hosts = []
            for host in hosts:
                try:
                    # Skip the local IP
                    if str(host) == self.local_ip:
                        continue
                    
                    # Try to ping the host
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", str(host)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=1
                    )
                    
                    # If ping was successful, add to alive hosts
                    if result.returncode == 0:
                        alive_hosts.append(str(host))
                except subprocess.TimeoutExpired:
                    # Timeout is expected for some hosts
                    pass
                except Exception as e:
                    logger.debug(f"Error pinging {host}: {e}")
            
            # Get MAC addresses for alive hosts
            for host in alive_hosts:
                try:
                    # Try to get MAC address from ARP table
                    result = subprocess.run(
                        ["arp", "-n", host],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=1
                    )
                    
                    # Parse MAC address from output
                    output = result.stdout
                    mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", output)
                    
                    if mac_match:
                        mac = mac_match.group(0)
                        device = {
                            "ip": host,
                            "mac": mac,
                            "last_seen": datetime.datetime.now().isoformat(),
                            "scan_method": "ping"
                        }
                        devices.append(device)
                except Exception as e:
                    logger.debug(f"Error getting MAC for {host}: {e}")
            
            logger.debug(f"Discovered {len(devices)} devices using ping sweep")
            return devices
        except Exception as e:
            logger.error(f"Error during ping scan: {e}")
            return []
    
    def _identify_device_type(self, hostname: str, vendor: str) -> str:
        """
        Identify the type of device based on hostname and vendor.
        
        Args:
            hostname: Device hostname
            vendor: Device vendor/manufacturer
            
        Returns:
            Device type string
        """
        hostname = hostname.lower()
        vendor = vendor.lower()
        combined = f"{hostname} {vendor}"
        
        # Check against device type patterns
        for device_type, patterns in DEVICE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined):
                    return device_type
        
        # Default type
        return "unknown"
    
    def _get_vendor_from_mac(self, mac: str) -> str:
        """
        Get the vendor/manufacturer from a MAC address.
        
        This is a simple implementation that matches the first three
        octets against a list of known vendors.
        
        Args:
            mac: MAC address
            
        Returns:
            Vendor name or "Unknown"
        """
        try:
            # Normalize MAC address format
            mac = mac.lower().replace('-', ':')
            
            # Get first three octets (OUI)
            oui = mac.split(':', 3)[:3]
            oui = ':'.join(oui)
            
            # Check OUI against known vendors
            # This is a very small subset of the full vendor database
            vendors = {
                "00:00:0c": "Cisco",
                "00:1a:11": "Google",
                "00:17:c8": "Apple",
                "00:16:6c": "Samsung",
                "00:15:5d": "Microsoft",
                "00:18:dd": "Hewlett-Packard",
                "00:12:17": "Cisco-Linksys",
                "00:14:22": "Dell",
                "00:1c:c4": "Intel",
                "00:1f:e2": "Broadcom",
                "00:21:ff": "Asus",
                "00:24:36": "Sony",
                "00:25:00": "Netgear",
                "00:26:37": "LG Electronics",
                "00:a0:c6": "Qualcomm",
                "04:4b:ed": "Xiaomi",
                "44:65:0d": "Amazon",
                "ec:1a:59": "Belkin",
                "fc:f5:c4": "TP-Link"
            }
            
            # Check if OUI is in our vendor list
            for vendor_oui, vendor_name in vendors.items():
                if mac.startswith(vendor_oui):
                    return vendor_name
            
            # If we don't have a match, try to use an online service
            # This would require an internet connection and API key
            # For a real implementation, consider using a local MAC vendor database
            
            return "Unknown"
        except Exception as e:
            logger.error(f"Error getting vendor from MAC: {e}")
            return "Unknown"
    
    def _get_hostname(self, ip: str) -> str:
        """
        Get the hostname for a device.
        
        Args:
            ip: IP address
            
        Returns:
            Hostname or empty string
        """
        try:
            # Try to get hostname using nslookup
            result = subprocess.run(
                ["nslookup", ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            
            # Parse hostname from output
            output = result.stdout
            hostname_match = re.search(r"name = ([\w.-]+)", output)
            
            if hostname_match:
                return hostname_match.group(1)
            
            # If nslookup fails, try using nbtscan (for Windows devices)
            try:
                result = subprocess.run(
                    ["nbtscan", ip],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2
                )
                
                # Parse hostname from output
                output = result.stdout
                hostname_match = re.search(r"\s+([\w-]+)\s+<", output)
                
                if hostname_match:
                    return hostname_match.group(1)
            except:
                # nbtscan might not be installed or might fail
                pass
            
            # If all else fails, return empty string
            return ""
        except Exception as e:
            logger.debug(f"Error getting hostname for {ip}: {e}")
            return ""
    
    def _enrich_device_data(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich device data with additional information.
        
        Args:
            devices: List of basic device data
            
        Returns:
            List of enriched device data
        """
        enriched_devices = []
        
        for device in devices:
            try:
                ip = device["ip"]
                mac = device["mac"]
                
                # Get device vendor from MAC
                vendor = self._get_vendor_from_mac(mac)
                
                # Get hostname
                hostname = self._get_hostname(ip)
                
                # Get device type
                device_type = self._identify_device_type(hostname, vendor)
                
                # Create enriched device record
                enriched_device = {
                    **device,
                    "hostname": hostname,
                    "vendor": vendor,
                    "device_type": device_type,
                    "first_seen": device.get("first_seen", device["last_seen"])
                }
                
                enriched_devices.append(enriched_device)
            except Exception as e:
                logger.error(f"Error enriching device data: {e}")
                enriched_devices.append(device)
        
        return enriched_devices
    
    def _merge_scan_results(self, arp_devices: List[Dict[str, Any]], 
                          ping_devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge results from different scan methods, avoiding duplicates.
        
        Args:
            arp_devices: Devices discovered via ARP
            ping_devices: Devices discovered via ping
            
        Returns:
            Merged list of devices
        """
        # Use MAC address as unique identifier
        devices_by_mac = {}
        
        # Process ARP devices first (preferred)
        for device in arp_devices:
            mac = device["mac"]
            devices_by_mac[mac] = device
        
        # Add ping devices if not already in the list
        for device in ping_devices:
            mac = device["mac"]
            if mac not in devices_by_mac:
                devices_by_mac[mac] = device
            else:
                # If we have data from both methods, update scan_method
                devices_by_mac[mac]["scan_method"] = "arp+ping"
        
        return list(devices_by_mac.values())
    
    def collect(self) -> Dict[str, Any]:
        """
        Collect device information from the network.
        
        Returns:
            Dictionary with discovered devices
        """
        logger.debug(f"Scanning network {self.network_cidr} for devices")
        
        try:
            # Scan using different methods
            arp_devices = self._scan_network_arp()
            ping_devices = self._scan_network_ping()
            
            # Merge results
            devices = self._merge_scan_results(arp_devices, ping_devices)
            
            # Enrich device data
            enriched_devices = self._enrich_device_data(devices)
            
            # Update known devices cache
            for device in enriched_devices:
                mac = device["mac"]
                if mac in self.known_devices:
                    # Update existing device
                    self.known_devices[mac].update(device)
                else:
                    # Add new device
                    self.known_devices[mac] = device
            
            # Prepare result
            data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "device_count": len(enriched_devices),
                "devices": enriched_devices
            }
            
            return data
        except Exception as e:
            logger.error(f"Error collecting device data: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat(),
                "device_count": 0,
                "devices": []
            }
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        Store the collected device data in MongoDB.
        
        Args:
            data: The collected device data
        """
        # Don't store if there was an error
        if "error" in data:
            logger.error(f"Not storing device data due to collection error: {data['error']}")
            return
        
        # Get devices from the data
        devices = data.get("devices", [])
        if not devices:
            logger.warning("No devices to store")
            return
        
        # Store devices in MongoDB
        for device in devices:
            try:
                # Use MAC as the primary identifier
                mac = device["mac"]
                
                # Get existing device from database
                existing_device = self.mongo_db.get_device_by_mac(mac)
                
                if existing_device:
                    # Update existing device
                    self.mongo_db.update_device(mac, {
                        # Keep the original first_seen date
                        "first_seen": existing_device.get("first_seen", device["last_seen"]),
                        # Update the last_seen date
                        "last_seen": device["last_seen"],
                        # Update other fields
                        "ip": device["ip"],
                        "hostname": device.get("hostname", existing_device.get("hostname", "")),
                        "vendor": device.get("vendor", existing_device.get("vendor", "Unknown")),
                        "device_type": device.get("device_type", existing_device.get("device_type", "unknown")),
                        # Add to IP history if different
                        "ip_history": self._update_ip_history(
                            existing_device.get("ip_history", []),
                            device["ip"],
                            device["last_seen"]
                        )
                    })
                else:
                    # Create new device
                    self.mongo_db.create_device({
                        "mac": mac,
                        "ip": device["ip"],
                        "hostname": device.get("hostname", ""),
                        "vendor": device.get("vendor", "Unknown"),
                        "device_type": device.get("device_type", "unknown"),
                        "first_seen": device["last_seen"],
                        "last_seen": device["last_seen"],
                        "ip_history": [{
                            "ip": device["ip"],
                            "first_seen": device["last_seen"],
                            "last_seen": device["last_seen"]
                        }]
                    })
            except Exception as e:
                logger.error(f"Error storing device {device.get('mac')}: {e}")
    
    def _update_ip_history(self, ip_history: List[Dict[str, Any]], 
                         current_ip: str, timestamp: str) -> List[Dict[str, Any]]:
        """
        Update the IP history for a device.
        
        Args:
            ip_history: Existing IP history
            current_ip: Current IP address
            timestamp: Current timestamp
            
        Returns:
            Updated IP history list
        """
        # Initialize history if empty
        if not ip_history:
            return [{
                "ip": current_ip,
                "first_seen": timestamp,
                "last_seen": timestamp
            }]
        
        # Check if the current IP is already in the history
        for entry in ip_history:
            if entry["ip"] == current_ip:
                # Update last_seen timestamp
                entry["last_seen"] = timestamp
                return ip_history
        
        # Add new IP to history
        ip_history.append({
            "ip": current_ip,
            "first_seen": timestamp,
            "last_seen": timestamp
        })
        
        return ip_history 