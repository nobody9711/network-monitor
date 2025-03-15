"""
Raspberry Pi Performance Collector
Collects system metrics like CPU, memory, disk usage, and temperature for Raspberry Pi
"""

import os
import psutil
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage

logger = logging.getLogger(__name__)

class PerformanceCollector(BaseCollector):
    """Collects Raspberry Pi system performance metrics."""
    
    def __init__(self, influx_db: InfluxDBStorage, collection_interval: int = 30):
        """
        Initialize the performance collector.
        
        Args:
            influx_db: InfluxDB storage instance
            collection_interval: How often to collect metrics (seconds)
        """
        super().__init__(collection_interval)
        self.influx_db = influx_db
        
        # Check if we're running on a Raspberry Pi
        self.is_raspberry_pi = self._check_raspberry_pi()
        if not self.is_raspberry_pi:
            logger.warning("Not running on a Raspberry Pi - some features may be limited")
        
        # Check temperature reading capability
        self.temp_file = "/sys/class/thermal/thermal_zone0/temp"
        self.can_read_temp = os.path.exists(self.temp_file)
        
        logger.info(f"Performance collector initialized. Raspberry Pi: {self.is_raspberry_pi}")
    
    def _check_raspberry_pi(self) -> bool:
        """Check if we're running on a Raspberry Pi."""
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read()
                return "Raspberry Pi" in model
        except Exception:
            return False
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature from the Raspberry Pi."""
        try:
            if self.can_read_temp:
                with open(self.temp_file, "r") as f:
                    temp = float(f.read().strip()) / 1000.0
                    return temp
            
            # Fallback to vcgencmd
            try:
                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    # Extract temperature value (e.g., "temp=45.7'C" -> 45.7)
                    temp = float(result.stdout.strip().split("=")[1].split("'")[0])
                    return temp
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            return None
        except Exception as e:
            logger.warning(f"Could not get CPU temperature: {e}")
            return None
    
    def _get_gpu_temperature(self) -> Optional[float]:
        """Get GPU temperature from the Raspberry Pi."""
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                temp = float(result.stdout.strip().split("=")[1].split("'")[0])
                return temp
            return None
        except Exception:
            return None
    
    def _get_throttling_status(self) -> Dict[str, bool]:
        """Get throttling status from the Raspberry Pi."""
        status = {
            "under_voltage": False,
            "freq_capped": False,
            "throttled": False,
            "soft_temp_limit": False
        }
        
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                # Parse throttling status
                throttled = int(result.stdout.strip().split("=")[1], 16)
                status["under_voltage"] = bool(throttled & 0x1)
                status["freq_capped"] = bool(throttled & 0x2)
                status["throttled"] = bool(throttled & 0x4)
                status["soft_temp_limit"] = bool(throttled & 0x8)
        except Exception as e:
            logger.warning(f"Could not get throttling status: {e}")
        
        return status
    
    def _get_cpu_freq(self) -> Dict[str, float]:
        """Get CPU frequency information."""
        try:
            freq = psutil.cpu_freq()
            return {
                "current": freq.current if freq else 0,
                "min": freq.min if freq else 0,
                "max": freq.max if freq else 0
            }
        except Exception:
            # Try using vcgencmd as fallback
            try:
                result = subprocess.run(
                    ["vcgencmd", "measure_clock", "arm"],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    # Convert Hz to MHz
                    freq = float(result.stdout.strip().split("=")[1]) / 1_000_000
                    return {"current": freq, "min": 0, "max": 0}
            except Exception:
                pass
            
            return {"current": 0, "min": 0, "max": 0}
    
    def _get_memory_voltage(self) -> Optional[float]:
        """Get memory voltage from the Raspberry Pi."""
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_volts", "core"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                # Extract voltage value (e.g., "volt=1.20V" -> 1.20)
                voltage = float(result.stdout.strip().split("=")[1].rstrip("V"))
                return voltage
            return None
        except Exception:
            return None
    
    def collect(self) -> Dict[str, Any]:
        """Collect Raspberry Pi system performance metrics."""
        try:
            # Get CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = self._get_cpu_freq()
            cpu_count = psutil.cpu_count()
            cpu_stats = psutil.cpu_stats()
            
            # Get memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Get disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Get temperature and throttling info
            cpu_temp = self._get_cpu_temperature()
            gpu_temp = self._get_gpu_temperature()
            throttling = self._get_throttling_status()
            memory_voltage = self._get_memory_voltage()
            
            # Get network metrics
            network = psutil.net_io_counters()
            
            # Get process count
            process_count = len(psutil.pids())
            
            # Get load average
            load_avg = os.getloadavg()
            
            # Compile metrics
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "frequency": cpu_freq["current"],
                    "min_freq": cpu_freq["min"],
                    "max_freq": cpu_freq["max"],
                    "count": cpu_count,
                    "ctx_switches": cpu_stats.ctx_switches,
                    "interrupts": cpu_stats.interrupts,
                    "soft_interrupts": cpu_stats.soft_interrupts,
                    "load_avg_1min": load_avg[0],
                    "load_avg_5min": load_avg[1],
                    "load_avg_15min": load_avg[2]
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free,
                    "swap_total": swap.total,
                    "swap_used": swap.used,
                    "swap_percent": swap.percent,
                    "voltage": memory_voltage
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                    "read_bytes": disk_io.read_bytes if disk_io else 0,
                    "write_bytes": disk_io.write_bytes if disk_io else 0,
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0
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
                "temperature": {
                    "cpu": cpu_temp,
                    "gpu": gpu_temp
                },
                "throttling": throttling,
                "system": {
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
                        "cpu_temperature": metrics["temperature"]["cpu"] if metrics["temperature"]["cpu"] is not None else 0,
                        "gpu_temperature": metrics["temperature"]["gpu"] if metrics["temperature"]["gpu"] is not None else 0,
                        "under_voltage": 1 if metrics["throttling"]["under_voltage"] else 0,
                        "freq_capped": 1 if metrics["throttling"]["freq_capped"] else 0,
                        "throttled": 1 if metrics["throttling"]["throttled"] else 0,
                        "process_count": metrics["system"]["process_count"],
                        "load_avg_1min": metrics["cpu"]["load_avg_1min"],
                        "load_avg_5min": metrics["cpu"]["load_avg_5min"]
                    }
                }
            ]
            
            # Store in InfluxDB
            self.influx_db.write_points(data_points)
            logger.debug("Performance metrics stored successfully")
        except Exception as e:
            logger.error(f"Error storing performance metrics: {e}", exc_info=True) 