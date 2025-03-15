"""
Security Analyzer - Detects network anomalies and potential threats
"""

import logging
import datetime
import ipaddress
from typing import Dict, Any, List, Optional, Set, Tuple

from src.database.mongo import MongoDBStorage
from src.database.influx import InfluxDBStorage
from src.security.alerts import AlertManager

logger = logging.getLogger(__name__)

# Known malicious port activities
SUSPICIOUS_PORTS = {
    # Commonly exploited ports
    22: "SSH",
    23: "Telnet",
    445: "SMB",
    1433: "MSSQL",
    3306: "MySQL",
    3389: "RDP",
    4444: "Metasploit",
    5900: "VNC",
    8080: "HTTP alternate",
    8443: "HTTPS alternate",
    9100: "Printer",
}

# Suspicious network behavior thresholds
THRESHOLDS = {
    "connection_rate": 30,        # Connections per minute
    "bandwidth_spike": 50.0,      # MB/s
    "port_scan_min_ports": 10,    # Minimum ports to consider a port scan
    "dns_query_rate": 100,        # DNS queries per minute
    "new_device_connections": 10, # Connections from a new device per minute
}

class SecurityAnalyzer:
    """
    Security Analyzer for Network Monitor.
    
    Analyzes network traffic and metrics to detect anomalies,
    potential security threats, and suspicious behavior.
    """
    
    def __init__(self, mongo_db: MongoDBStorage, influx_db: InfluxDBStorage,
                alert_manager: AlertManager, bandwidth_threshold: float = 50.0,
                cpu_threshold: float = 90.0):
        """
        Initialize the Security Analyzer.
        
        Args:
            mongo_db: MongoDB storage instance
            influx_db: InfluxDB storage instance
            alert_manager: Alert manager instance
            bandwidth_threshold: Bandwidth threshold in MB/s
            cpu_threshold: CPU usage threshold percentage
        """
        self.mongo_db = mongo_db
        self.influx_db = influx_db
        self.alert_manager = alert_manager
        self.bandwidth_threshold = bandwidth_threshold
        self.cpu_threshold = cpu_threshold
        
        # Internal state
        self.known_ips = set()  # IPs that have been seen before
        self.device_history = {}  # Historical device activity
        self.port_scan_cache = {}  # Track potential port scan activity
        self.bandwidth_history = []  # Recent bandwidth usage
        
        # Load known devices and IP addresses
        self._load_known_devices()
    
    def _load_known_devices(self) -> None:
        """Load known devices from the database."""
        devices = self.mongo_db.get_all_devices()
        for device in devices:
            self.known_ips.add(device["ip"])
            
            # Initialize device history
            mac = device["mac"]
            if mac not in self.device_history:
                self.device_history[mac] = {
                    "connections": [],
                    "bandwidth": [],
                    "avg_connections_per_hour": 0,
                    "avg_bandwidth_mbps": 0,
                    "common_ports": set(),
                    "common_destinations": set()
                }
    
    def analyze(self) -> None:
        """
        Perform security analysis on the network.
        
        This method analyzes various network metrics to detect
        potential security issues and trigger alerts if necessary.
        """
        logger.info("Running security analysis")
        
        try:
            # Get current timestamp
            now = datetime.datetime.now()
            timestamp = now.isoformat()
            
            # Analyze new devices
            self._analyze_new_devices()
            
            # Analyze bandwidth usage for anomalies
            self._analyze_bandwidth()
            
            # Analyze connection patterns
            self._analyze_connection_patterns()
            
            # Analyze system performance
            self._analyze_system_performance()
            
            # Analyze DNS queries if Pi-hole is enabled
            self._analyze_dns_queries()
            
            # Clean up old cache entries
            self._cleanup_cache()
            
            logger.info("Security analysis completed")
        except Exception as e:
            logger.error(f"Error during security analysis: {e}", exc_info=True)
    
    def _analyze_new_devices(self) -> None:
        """Analyze new devices that have appeared on the network."""
        # Get recently seen devices
        recent_devices = self.mongo_db.get_active_devices(hours=1)
        
        # Check for new devices
        for device in recent_devices:
            ip = device["ip"]
            mac = device["mac"]
            
            # If this IP isn't in our known list, it's potentially new
            if ip not in self.known_ips:
                self._handle_new_device(device)
                
                # Add to known IPs
                self.known_ips.add(ip)
    
    def _handle_new_device(self, device: Dict[str, Any]) -> None:
        """
        Handle a newly discovered device.
        
        Args:
            device: The device data
        """
        ip = device["ip"]
        mac = device["mac"]
        hostname = device.get("hostname", "Unknown")
        vendor = device.get("vendor", "Unknown")
        device_type = device.get("device_type", "unknown")
        first_seen = device.get("first_seen", datetime.datetime.now().isoformat())
        
        # Try to determine if this is suspicious
        is_suspicious = False
        suspicion_reasons = []
        
        # Check if the device has a suspicious vendor
        suspicious_vendors = ["unknown", "raspberrypi", "arduino", "espressif"]
        if vendor.lower() in suspicious_vendors:
            is_suspicious = True
            suspicion_reasons.append(f"Suspicious vendor: {vendor}")
        
        # Check if the device has a suspicious hostname
        suspicious_hostnames = ["kali", "parrot", "pentoo", "blackarch", "test", "admin"]
        if any(s in hostname.lower() for s in suspicious_hostnames):
            is_suspicious = True
            suspicion_reasons.append(f"Suspicious hostname: {hostname}")
        
        # Check if the device appears to be spoofing another device's MAC
        if mac in self.device_history:
            # This MAC has been seen before, but with a different IP
            previous_ips = set()
            for entry in self.device_history[mac].get("connections", []):
                if "ip" in entry:
                    previous_ips.add(entry["ip"])
            
            if ip not in previous_ips and previous_ips:
                is_suspicious = True
                suspicion_reasons.append(f"MAC address previously seen with different IPs: {previous_ips}")
        
        # Determine alert severity
        severity = "medium" if is_suspicious else "low"
        
        # Create alert message
        if is_suspicious:
            message = f"Suspicious new device detected: {hostname} ({ip}, {mac})"
            details = {
                "message": message,
                "suspicion_reasons": suspicion_reasons,
                "first_seen": first_seen
            }
        else:
            message = f"New device connected to the network: {hostname} ({ip}, {mac})"
            details = {
                "message": message,
                "first_seen": first_seen
            }
        
        # Trigger alert
        self.alert_manager.trigger_alert(
            event_type="new_device",
            severity=severity,
            details=details,
            source_device=device
        )
        
        # Log event
        self.mongo_db.create_event({
            "event_type": "new_device",
            "timestamp": datetime.datetime.now().isoformat(),
            "severity": severity,
            "source_ip": ip,
            "source_mac": mac,
            "message": message,
            "details": details
        })
        
        # Initialize device history
        if mac not in self.device_history:
            self.device_history[mac] = {
                "connections": [],
                "bandwidth": [],
                "avg_connections_per_hour": 0,
                "avg_bandwidth_mbps": 0,
                "common_ports": set(),
                "common_destinations": set()
            }
    
    def _analyze_bandwidth(self) -> None:
        """Analyze bandwidth usage for anomalies."""
        # Get recent bandwidth metrics
        now = datetime.datetime.now()
        start_time = (now - datetime.timedelta(minutes=15)).isoformat()
        bandwidth_metrics = self.influx_db.get_bandwidth_metrics(start_time=start_time)
        
        if not bandwidth_metrics:
            return
        
        # Calculate average and peak bandwidth
        total_bandwidth = sum(bw.get("total_bps", 0) for bw in bandwidth_metrics)
        avg_bandwidth_bps = total_bandwidth / len(bandwidth_metrics)
        avg_bandwidth_mbps = avg_bandwidth_bps / 1_000_000
        
        peak_bandwidth_bps = max(bw.get("total_bps", 0) for bw in bandwidth_metrics)
        peak_bandwidth_mbps = peak_bandwidth_bps / 1_000_000
        
        # Check for bandwidth anomalies
        if peak_bandwidth_mbps > self.bandwidth_threshold:
            # This is a high bandwidth event
            message = f"High bandwidth usage detected: {peak_bandwidth_mbps:.2f} Mbps"
            details = {
                "message": message,
                "peak_bandwidth_mbps": peak_bandwidth_mbps,
                "avg_bandwidth_mbps": avg_bandwidth_mbps,
                "threshold_mbps": self.bandwidth_threshold
            }
            
            # Determine severity based on how much it exceeds the threshold
            if peak_bandwidth_mbps > self.bandwidth_threshold * 2:
                severity = "high"
            elif peak_bandwidth_mbps > self.bandwidth_threshold * 1.5:
                severity = "medium"
            else:
                severity = "low"
            
            # Trigger alert
            self.alert_manager.trigger_alert(
                event_type="high_bandwidth",
                severity=severity,
                details=details
            )
            
            # Log event
            self.mongo_db.create_event({
                "event_type": "high_bandwidth",
                "timestamp": datetime.datetime.now().isoformat(),
                "severity": severity,
                "message": message,
                "details": details
            })
        
        # Add to bandwidth history
        self.bandwidth_history.append({
            "timestamp": now.isoformat(),
            "avg_mbps": avg_bandwidth_mbps,
            "peak_mbps": peak_bandwidth_mbps
        })
        
        # Trim history to keep only the last 24 hours
        one_day_ago = now - datetime.timedelta(days=1)
        self.bandwidth_history = [
            entry for entry in self.bandwidth_history
            if datetime.datetime.fromisoformat(entry["timestamp"]) > one_day_ago
        ]
    
    def _analyze_connection_patterns(self) -> None:
        """Analyze connection patterns for anomalies."""
        # Get recent connections
        active_devices = self.mongo_db.get_active_devices(hours=1)
        
        # Group connections by device
        device_connections = {}
        for device in active_devices:
            mac = device["mac"]
            if mac not in device_connections:
                device_connections[mac] = []
            
            # Add connection events from device history if available
            events = self.mongo_db.get_events_by_device(device["ip"], mac, limit=100)
            for event in events:
                if event["event_type"] == "connection":
                    device_connections[mac].append(event)
        
        # Analyze each device's connections
        for mac, connections in device_connections.items():
            if not connections:
                continue
            
            # Check for port scanning behavior
            self._check_port_scan(mac, connections)
            
            # Check for unusual connection rates
            self._check_connection_rate(mac, connections)
            
            # Check for connections to unusual destinations
            self._check_unusual_destinations(mac, connections)
    
    def _check_port_scan(self, mac: str, connections: List[Dict[str, Any]]) -> None:
        """
        Check for port scanning behavior.
        
        Args:
            mac: Device MAC address
            connections: List of connection events
        """
        # Get most recent connection timestamp
        most_recent = max(
            datetime.datetime.fromisoformat(conn["timestamp"])
            for conn in connections
        )
        
        # Initialize port scan cache for this device if not exists
        if mac not in self.port_scan_cache:
            self.port_scan_cache[mac] = {
                "targets": {},
                "last_alert": None
            }
        
        # Group connections by target
        targets = {}
        for conn in connections:
            # Extract data from connection
            if "target_ip" not in conn:
                continue
            
            target_ip = conn["target_ip"]
            port = conn.get("target_port")
            timestamp = conn["timestamp"]
            
            if port is None:
                continue
            
            # Add to targets
            if target_ip not in targets:
                targets[target_ip] = {"ports": set(), "timestamps": []}
            
            targets[target_ip]["ports"].add(port)
            targets[target_ip]["timestamps"].append(timestamp)
        
        # Update port scan cache
        for target_ip, data in targets.items():
            # Update cache
            if target_ip not in self.port_scan_cache[mac]["targets"]:
                self.port_scan_cache[mac]["targets"][target_ip] = {
                    "ports": set(),
                    "first_seen": datetime.datetime.now().isoformat()
                }
            
            self.port_scan_cache[mac]["targets"][target_ip]["ports"].update(data["ports"])
            
            # Check if this looks like a port scan
            port_count = len(self.port_scan_cache[mac]["targets"][target_ip]["ports"])
            
            if port_count >= THRESHOLDS["port_scan_min_ports"]:
                # This looks like a port scan
                last_alert = self.port_scan_cache[mac]["last_alert"]
                
                # Don't alert more than once per hour for the same device
                if not last_alert or (
                    datetime.datetime.now() - 
                    datetime.datetime.fromisoformat(last_alert)
                ).total_seconds() > 3600:
                    # Get device info
                    device = self.mongo_db.get_device_by_mac(mac)
                    
                    if device:
                        # Create alert
                        message = f"Potential port scan detected from {device.get('hostname', mac)} ({device['ip']}) to {target_ip}"
                        details = {
                            "message": message,
                            "scanned_ports": list(self.port_scan_cache[mac]["targets"][target_ip]["ports"]),
                            "port_count": port_count,
                            "first_seen": self.port_scan_cache[mac]["targets"][target_ip]["first_seen"]
                        }
                        
                        # Trigger alert
                        self.alert_manager.trigger_alert(
                            event_type="port_scan",
                            severity="medium",
                            details=details,
                            source_device=device
                        )
                        
                        # Log event
                        self.mongo_db.create_event({
                            "event_type": "port_scan",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "severity": "medium",
                            "source_ip": device["ip"],
                            "source_mac": mac,
                            "target_ip": target_ip,
                            "message": message,
                            "details": details
                        })
                        
                        # Update last alert
                        self.port_scan_cache[mac]["last_alert"] = datetime.datetime.now().isoformat()
    
    def _check_connection_rate(self, mac: str, connections: List[Dict[str, Any]]) -> None:
        """
        Check for unusual connection rates.
        
        Args:
            mac: Device MAC address
            connections: List of connection events
        """
        # Get connection timestamps in the last minute
        now = datetime.datetime.now()
        one_minute_ago = now - datetime.timedelta(minutes=1)
        
        recent_connections = [
            conn for conn in connections
            if datetime.datetime.fromisoformat(conn["timestamp"]) > one_minute_ago
        ]
        
        # Check connection rate
        connection_rate = len(recent_connections)
        
        if connection_rate > THRESHOLDS["connection_rate"]:
            # Unusually high connection rate
            device = self.mongo_db.get_device_by_mac(mac)
            
            if device:
                # Create alert
                message = f"High connection rate detected from {device.get('hostname', mac)} ({device['ip']}): {connection_rate} connections/minute"
                details = {
                    "message": message,
                    "connection_rate": connection_rate,
                    "threshold": THRESHOLDS["connection_rate"]
                }
                
                # Trigger alert
                self.alert_manager.trigger_alert(
                    event_type="high_connection_rate",
                    severity="medium",
                    details=details,
                    source_device=device
                )
                
                # Log event
                self.mongo_db.create_event({
                    "event_type": "high_connection_rate",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "severity": "medium",
                    "source_ip": device["ip"],
                    "source_mac": mac,
                    "message": message,
                    "details": details
                })
    
    def _check_unusual_destinations(self, mac: str, connections: List[Dict[str, Any]]) -> None:
        """
        Check for connections to unusual destinations.
        
        Args:
            mac: Device MAC address
            connections: List of connection events
        """
        # Initialize device history if needed
        if mac not in self.device_history:
            self.device_history[mac] = {
                "connections": [],
                "common_destinations": set()
            }
        
        # Get common destinations for this device
        common_destinations = self.device_history[mac].get("common_destinations", set())
        
        # Check each connection for unusual destinations
        for conn in connections:
            if "target_ip" not in conn:
                continue
            
            target_ip = conn["target_ip"]
            port = conn.get("target_port")
            
            if not port:
                continue
            
            # Skip if this is a common destination
            if f"{target_ip}:{port}" in common_destinations:
                continue
            
            # Check if the port is known to be suspicious
            if port in SUSPICIOUS_PORTS:
                device = self.mongo_db.get_device_by_mac(mac)
                
                if device:
                    # Create alert
                    message = f"Connection to suspicious port detected from {device.get('hostname', mac)} ({device['ip']}): {target_ip}:{port} ({SUSPICIOUS_PORTS[port]})"
                    details = {
                        "message": message,
                        "target_ip": target_ip,
                        "port": port,
                        "service": SUSPICIOUS_PORTS[port]
                    }
                    
                    # Trigger alert
                    self.alert_manager.trigger_alert(
                        event_type="suspicious_connection",
                        severity="medium",
                        details=details,
                        source_device=device
                    )
                    
                    # Log event
                    self.mongo_db.create_event({
                        "event_type": "suspicious_connection",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "severity": "medium",
                        "source_ip": device["ip"],
                        "source_mac": mac,
                        "target_ip": target_ip,
                        "target_port": port,
                        "message": message,
                        "details": details
                    })
            else:
                # Add to common destinations
                common_destinations.add(f"{target_ip}:{port}")
        
        # Update device history
        self.device_history[mac]["common_destinations"] = common_destinations
    
    def _analyze_system_performance(self) -> None:
        """Analyze system performance for anomalies."""
        # Get recent performance metrics
        recent_performance = self.influx_db.get_recent_performance(minutes=5)
        
        if not recent_performance or "error" in recent_performance:
            return
        
        # Check CPU usage
        cpu_percent = recent_performance.get("cpu_percent", 0)
        
        if cpu_percent > self.cpu_threshold:
            # High CPU usage
            message = f"High CPU usage detected: {cpu_percent:.1f}%"
            details = {
                "message": message,
                "cpu_percent": cpu_percent,
                "threshold": self.cpu_threshold
            }
            
            # Determine severity based on how much it exceeds the threshold
            if cpu_percent > self.cpu_threshold + 5:
                severity = "high"
            else:
                severity = "medium"
            
            # Trigger alert
            self.alert_manager.trigger_alert(
                event_type="high_cpu_usage",
                severity=severity,
                details=details
            )
            
            # Log event
            self.mongo_db.create_event({
                "event_type": "high_cpu_usage",
                "timestamp": datetime.datetime.now().isoformat(),
                "severity": severity,
                "message": message,
                "details": details
            })
    
    def _analyze_dns_queries(self) -> None:
        """Analyze DNS queries for anomalies."""
        # Check if Pi-hole integration is available
        pihole_stats = self.influx_db.get_pihole_summary()
        
        if not pihole_stats or "error" in pihole_stats:
            return
        
        # Get total queries in the last day
        total_queries = pihole_stats.get("dns_queries_today", 0)
        
        # Calculate average query rate (queries per minute)
        query_rate = total_queries / (24 * 60)  # Assuming this is for a 24-hour period
        
        if query_rate > THRESHOLDS["dns_query_rate"]:
            # High DNS query rate
            message = f"High DNS query rate detected: {query_rate:.1f} queries/minute"
            details = {
                "message": message,
                "query_rate": query_rate,
                "threshold": THRESHOLDS["dns_query_rate"],
                "total_queries": total_queries
            }
            
            # Trigger alert
            self.alert_manager.trigger_alert(
                event_type="high_dns_query_rate",
                severity="medium",
                details=details
            )
            
            # Log event
            self.mongo_db.create_event({
                "event_type": "high_dns_query_rate",
                "timestamp": datetime.datetime.now().isoformat(),
                "severity": "medium",
                "message": message,
                "details": details
            })
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        # Get current time
        now = datetime.datetime.now()
        
        # Clean up port scan cache
        # Remove entries older than 24 hours
        for mac in list(self.port_scan_cache.keys()):
            # Clean up targets
            for target_ip in list(self.port_scan_cache[mac]["targets"].keys()):
                first_seen = self.port_scan_cache[mac]["targets"][target_ip]["first_seen"]
                try:
                    first_seen_dt = datetime.datetime.fromisoformat(first_seen)
                    if (now - first_seen_dt).total_seconds() > 86400:  # 24 hours
                        del self.port_scan_cache[mac]["targets"][target_ip]
                except ValueError:
                    # Invalid timestamp, remove entry
                    del self.port_scan_cache[mac]["targets"][target_ip]
            
            # Remove devices with no targets
            if not self.port_scan_cache[mac]["targets"]:
                del self.port_scan_cache[mac] 