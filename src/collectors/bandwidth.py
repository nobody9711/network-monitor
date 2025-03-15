"""
Bandwidth Collector - Monitors network traffic and bandwidth usage
"""

import time
import logging
import socket
import datetime
import subprocess
from typing import Dict, Any, List, Optional, Tuple

import psutil
import scapy.all as scapy
from scapy.layers.inet import IP

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage

logger = logging.getLogger(__name__)

class BandwidthCollector(BaseCollector):
    """
    Collector for network bandwidth and traffic data.
    
    Monitors network traffic by interface, collects statistics about
    bandwidth usage, connections, and provides traffic analysis.
    """
    
    def __init__(self, interface: str, influx_db: InfluxDBStorage, interval: int = 5):
        """
        Initialize the bandwidth collector.
        
        Args:
            interface: Network interface to monitor
            influx_db: InfluxDB storage instance
            interval: Collection interval in seconds
        """
        super().__init__(interval=interval)
        self.interface = interface
        self.influx_db = influx_db
        self._prev_io_counters = self._get_io_counters()
        self._connections_cache = {}
        self._connection_history = []
        
        # Set up packet capture if available
        self.enable_packet_capture = True
        try:
            # Test if we have permission to capture packets
            test_capture = scapy.sniff(iface=self.interface, count=1, timeout=2)
            if not test_capture:
                logger.warning("Packet capture test failed, disabling detailed traffic analysis")
                self.enable_packet_capture = False
        except Exception as e:
            logger.warning(f"Failed to initialize packet capture: {e}")
            self.enable_packet_capture = False
    
    def _get_io_counters(self) -> Dict[str, int]:
        """
        Get current network IO counters for the monitored interface.
        
        Returns:
            Dict with bytes_sent, bytes_recv, packets_sent, packets_recv
        """
        io_counters = psutil.net_io_counters(pernic=True).get(self.interface)
        if not io_counters:
            logger.error(f"Interface {self.interface} not found")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0
            }
        
        return {
            "bytes_sent": io_counters.bytes_sent,
            "bytes_recv": io_counters.bytes_recv,
            "packets_sent": io_counters.packets_sent,
            "packets_recv": io_counters.packets_recv
        }
    
    def _get_bandwidth_stats(self) -> Dict[str, float]:
        """
        Calculate bandwidth usage since the last collection.
        
        Returns:
            Dict with upload_bps, download_bps, total_bps
        """
        current = self._get_io_counters()
        prev = self._prev_io_counters
        
        # Calculate elapsed time since last collection
        elapsed = self.interval
        
        # Calculate bandwidth in bits per second
        upload_bytes = current["bytes_sent"] - prev["bytes_sent"]
        download_bytes = current["bytes_recv"] - prev["bytes_recv"]
        
        upload_bps = (upload_bytes * 8) / elapsed
        download_bps = (download_bytes * 8) / elapsed
        total_bps = upload_bps + download_bps
        
        # Update previous counters
        self._prev_io_counters = current
        
        return {
            "upload_bps": upload_bps,
            "download_bps": download_bps, 
            "total_bps": total_bps,
            "upload_bytes": upload_bytes,
            "download_bytes": download_bytes
        }
    
    def _get_active_connections(self) -> List[Dict[str, Any]]:
        """
        Get list of active network connections.
        
        Returns:
            List of connection details
        """
        connections = []
        
        # Get current connections
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'ESTABLISHED':
                try:
                    # Extract connection details
                    local_ip, local_port = conn.laddr
                    remote_ip, remote_port = conn.raddr
                    
                    # Try to resolve remote hostname
                    remote_host = remote_ip
                    try:
                        remote_host = socket.gethostbyaddr(remote_ip)[0]
                    except (socket.herror, socket.gaierror):
                        pass
                    
                    # Create connection record
                    connection = {
                        "local_ip": local_ip,
                        "local_port": local_port,
                        "remote_ip": remote_ip,
                        "remote_port": remote_port,
                        "remote_host": remote_host,
                        "pid": conn.pid,
                        "status": conn.status,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    # Add process name if available
                    if conn.pid:
                        try:
                            connection["process"] = psutil.Process(conn.pid).name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            connection["process"] = "unknown"
                    
                    # Add to connections list
                    connections.append(connection)
                    
                    # Update connection cache
                    conn_key = f"{local_ip}:{local_port}-{remote_ip}:{remote_port}"
                    self._connections_cache[conn_key] = connection
                except Exception as e:
                    logger.warning(f"Error processing connection: {e}")
        
        return connections
    
    def _analyze_traffic(self, duration: int = 5) -> Dict[str, Any]:
        """
        Capture and analyze network traffic.
        
        Args:
            duration: Duration of traffic capture in seconds
            
        Returns:
            Dictionary with traffic analysis results
        """
        if not self.enable_packet_capture:
            return {
                "error": "Packet capture disabled",
                "protocols": {},
                "ips": {}
            }
        
        try:
            # Capture packets for the specified duration
            logger.debug(f"Capturing packets on {self.interface} for {duration} seconds")
            packets = scapy.sniff(iface=self.interface, timeout=duration)
            logger.debug(f"Captured {len(packets)} packets")
            
            # Initialize counters
            protocols = {}
            source_ips = {}
            dest_ips = {}
            total_bytes = 0
            
            # Analyze packets
            for packet in packets:
                # Skip non-IP packets
                if IP not in packet:
                    continue
                
                # Count by protocol
                proto = packet[IP].proto
                proto_name = {1: "ICMP", 6: "TCP", 17: "UDP"}.get(proto, str(proto))
                protocols[proto_name] = protocols.get(proto_name, 0) + 1
                
                # Count by source IP
                src_ip = packet[IP].src
                source_ips[src_ip] = source_ips.get(src_ip, 0) + 1
                
                # Count by destination IP
                dst_ip = packet[IP].dst
                dest_ips[dst_ip] = dest_ips.get(dst_ip, 0) + 1
                
                # Count total bytes
                total_bytes += len(packet)
            
            # Prepare results
            return {
                "packet_count": len(packets),
                "total_bytes": total_bytes,
                "protocols": protocols,
                "source_ips": dict(sorted(source_ips.items(), key=lambda x: x[1], reverse=True)[:10]),
                "dest_ips": dict(sorted(dest_ips.items(), key=lambda x: x[1], reverse=True)[:10])
            }
        except Exception as e:
            logger.error(f"Error during traffic analysis: {e}")
            return {
                "error": str(e),
                "protocols": {},
                "ips": {}
            }
    
    def _run_speedtest(self) -> Dict[str, Any]:
        """
        Run a speed test to measure internet connection speed.
        
        This is resource-intensive, so it should be run infrequently.
        
        Returns:
            Dictionary with speed test results
        """
        try:
            # Run speedtest-cli in a subprocess
            logger.info("Running speed test...")
            result = subprocess.run(
                ["speedtest-cli", "--json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse JSON output
            import json
            data = json.loads(result.stdout)
            
            # Extract relevant data
            return {
                "download": data["download"] / 1_000_000,  # Convert to Mbps
                "upload": data["upload"] / 1_000_000,      # Convert to Mbps
                "ping": data["ping"],
                "server": data["server"]["sponsor"],
                "timestamp": data["timestamp"]
            }
        except subprocess.TimeoutExpired:
            logger.error("Speed test timed out")
            return {"error": "Speed test timed out"}
        except subprocess.SubprocessError as e:
            logger.error(f"Error running speed test: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error processing speed test results: {e}")
            return {"error": str(e)}
    
    def collect(self) -> Dict[str, Any]:
        """
        Collect bandwidth and network traffic data.
        
        Returns:
            Dictionary with collected network data
        """
        logger.debug(f"Collecting bandwidth data for interface {self.interface}")
        
        try:
            # Get bandwidth statistics
            bandwidth_stats = self._get_bandwidth_stats()
            
            # Get active connections
            connections = self._get_active_connections()
            
            # Basic traffic analysis based on connections
            traffic_analysis = {
                "connection_count": len(connections),
                "connection_details": connections[:10]  # Limit to 10 connections
            }
            
            # Detailed traffic analysis if packet capture is enabled
            if self.enable_packet_capture:
                traffic_analysis.update(self._analyze_traffic(duration=1))
            
            # Combine all data
            data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "bandwidth": bandwidth_stats,
                "connections": traffic_analysis,
            }
            
            # Run speed test every hour (approximately)
            # We use a simple heuristic: if the current minute is 0
            # This isn't precise, but it's good enough
            current_minute = datetime.datetime.now().minute
            if current_minute == 0:
                speed_test = self._run_speedtest()
                data["speed_test"] = speed_test
            
            return data
        except Exception as e:
            logger.error(f"Error collecting bandwidth data: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        Store the collected bandwidth data in InfluxDB.
        
        Args:
            data: The collected bandwidth data
        """
        timestamp = data.get("timestamp")
        if not timestamp:
            timestamp = datetime.datetime.now().isoformat()
        
        # Don't store if there was an error
        if "error" in data:
            logger.error(f"Not storing bandwidth data due to collection error: {data['error']}")
            return
        
        # Store bandwidth metrics
        bandwidth = data.get("bandwidth", {})
        self.influx_db.write_bandwidth_metrics(
            upload_bps=bandwidth.get("upload_bps", 0),
            download_bps=bandwidth.get("download_bps", 0),
            total_bps=bandwidth.get("total_bps", 0),
            upload_bytes=bandwidth.get("upload_bytes", 0),
            download_bytes=bandwidth.get("download_bytes", 0),
            timestamp=timestamp
        )
        
        # Store connection metrics
        connections = data.get("connections", {})
        self.influx_db.write_connection_metrics(
            connection_count=connections.get("connection_count", 0),
            timestamp=timestamp
        )
        
        # Store protocol distribution if available
        protocols = connections.get("protocols", {})
        if protocols:
            for protocol, count in protocols.items():
                self.influx_db.write_protocol_metrics(
                    protocol=protocol,
                    count=count,
                    timestamp=timestamp
                )
        
        # Store speed test results if available
        speed_test = data.get("speed_test", {})
        if speed_test and "error" not in speed_test:
            self.influx_db.write_speedtest_metrics(
                download_mbps=speed_test.get("download", 0),
                upload_mbps=speed_test.get("upload", 0),
                ping_ms=speed_test.get("ping", 0),
                server=speed_test.get("server", "unknown"),
                timestamp=timestamp
            ) 