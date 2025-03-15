"""
Windows System Performance Collector
Collects system metrics like CPU, memory, disk usage, and temperature for Windows systems
"""

import psutil
import logging
import wmi
import time
from datetime import datetime
from typing import Dict, Any, Optional

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage

logger = logging.getLogger(__name__)

class PerformanceCollector(BaseCollector):
    """Collects Windows system performance metrics."""
    
    def __init__(self, influx_db: InfluxDBStorage, collection_interval: int = 30):
        """
        Initialize the performance collector.
        
        Args:
            influx_db: InfluxDB storage instance
            collection_interval: How often to collect metrics (seconds)
        """
        super().__init__(collection_interval)
        self.influx_db = influx_db
        self.wmi_client = None
        try:
            self.wmi_client = wmi.WMI()
            logger.info("WMI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WMI client: {e}")
    
    def collect(self) -> Dict[str, Any]:
        """Collect Windows system performance metrics."""
        try:
            # Get CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            cpu_stats = psutil.cpu_stats()
            
            # Get memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Get disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Get system temperature if available
            temperature = self._get_system_temperature()
            
            # Get network metrics
            network = psutil.net_io_counters()
            
            # Get process count
            process_count = len(psutil.pids())
            
            # Compile metrics
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "frequency": cpu_freq.current if cpu_freq else 0,
                    "ctx_switches": cpu_stats.ctx_switches,
                    "interrupts": cpu_stats.interrupts,
                    "soft_interrupts": cpu_stats.soft_interrupts,
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free,
                    "swap_total": swap.total,
                    "swap_used": swap.used,
                    "swap_percent": swap.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                    "read_bytes": disk_io.read_bytes,
                    "write_bytes": disk_io.write_bytes,
                    "read_count": disk_io.read_count,
                    "write_count": disk_io.write_count
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                    "errin": network.errin,
                    "errout": network.errout,
                    "dropin": network.dropin,
                    "dropout": network.dropout
                },
                "system": {
                    "temperature": temperature,
                    "process_count": process_count,
                    "boot_time": psutil.boot_time()
                }
            }
            
            # Store metrics in InfluxDB
            self.store_data(metrics)
            
            return metrics
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _get_system_temperature(self) -> Optional[float]:
        """
        Get system temperature using WMI.
        Returns None if temperature cannot be retrieved.
        """
        try:
            if not self.wmi_client:
                return None
            
            # Try to get CPU temperature from various sources
            temperature_sources = [
                "Win32_TemperatureProbe",
                "MSAcpi_ThermalZoneTemperature",
                "Win32_PerfFormattedData_Counters_ThermalZoneInformation"
            ]
            
            for source in temperature_sources:
                try:
                    temps = self.wmi_client.query(f"SELECT * FROM {source}")
                    for temp in temps:
                        if hasattr(temp, "CurrentTemperature"):
                            # Convert temperature to Celsius if needed
                            return temp.CurrentTemperature / 10.0 - 273.15
                        elif hasattr(temp, "Temperature"):
                            return temp.Temperature / 10.0 - 273.15
                except Exception:
                    continue
            
            return None
        except Exception as e:
            logger.warning(f"Could not get system temperature: {e}")
            return None
    
    def store_data(self, metrics: Dict[str, Any]) -> None:
        """
        Store performance metrics in InfluxDB.
        
        Args:
            metrics: Dictionary of metrics to store
        """
        try:
            # Format metrics for InfluxDB
            data_points = [
                {
                    "measurement": "system_performance",
                    "time": metrics["timestamp"],
                    "fields": {
                        "cpu_percent": metrics["cpu"]["percent"],
                        "cpu_frequency": metrics["cpu"]["frequency"],
                        "memory_percent": metrics["memory"]["percent"],
                        "memory_used": metrics["memory"]["used"],
                        "memory_free": metrics["memory"]["free"],
                        "swap_percent": metrics["memory"]["swap_percent"],
                        "disk_percent": metrics["disk"]["percent"],
                        "disk_used": metrics["disk"]["used"],
                        "disk_free": metrics["disk"]["free"],
                        "network_bytes_sent": metrics["network"]["bytes_sent"],
                        "network_bytes_recv": metrics["network"]["bytes_recv"],
                        "temperature": metrics["system"]["temperature"] if metrics["system"]["temperature"] is not None else 0,
                        "process_count": metrics["system"]["process_count"]
                    }
                }
            ]
            
            # Store in InfluxDB
            self.influx_db.write_points(data_points)
            logger.debug("Performance metrics stored successfully")
        except Exception as e:
            logger.error(f"Error storing performance metrics: {e}", exc_info=True)
    
    def _get_disk_smart_info(self) -> Dict[str, Any]:
        """
        Get SMART disk information using WMI.
        This is Windows-specific and may require admin privileges.
        """
        try:
            if not self.wmi_client:
                return {}
            
            disk_info = {}
            physical_disks = self.wmi_client.query("SELECT * FROM Win32_DiskDrive")
            
            for disk in physical_disks:
                disk_info[disk.DeviceID] = {
                    "model": disk.Model,
                    "size": disk.Size,
                    "status": disk.Status,
                    "interface_type": disk.InterfaceType,
                    "media_type": disk.MediaType,
                    "partitions": disk.Partitions,
                    "serial": disk.SerialNumber
                }
            
            return disk_info
        except Exception as e:
            logger.warning(f"Could not get SMART disk info: {e}")
            return {} 