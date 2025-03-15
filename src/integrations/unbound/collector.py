"""
Unbound Integration - Collects metrics from Unbound DNS resolver
"""

import logging
import datetime
import subprocess
import re
from typing import Dict, Any, Optional, List, Tuple

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage

logger = logging.getLogger(__name__)

class UnboundCollector(BaseCollector):
    """
    Collector for Unbound DNS resolver metrics.
    
    Retrieves statistics and metrics from Unbound using
    the unbound-control tool.
    """
    
    def __init__(self, control_path: str, influx_db: InfluxDBStorage,
                interval: int = 10):
        """
        Initialize the Unbound collector.
        
        Args:
            control_path: Path to unbound-control executable
            influx_db: InfluxDB storage instance
            interval: Collection interval in seconds
        """
        super().__init__(interval=interval)
        self.control_path = control_path
        self.influx_db = influx_db
        
        # Check if unbound-control is available
        self.available = self._check_availability()
        
        if not self.available:
            logger.warning("unbound-control is not available, Unbound metrics collection disabled")
    
    def _check_availability(self) -> bool:
        """
        Check if unbound-control is available and working.
        
        Returns:
            True if available, False otherwise
        """
        try:
            # Run unbound-control version
            result = subprocess.run(
                [self.control_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Check if command succeeded
            if result.returncode != 0:
                logger.error(f"Error running unbound-control: {result.stderr}")
                return False
            
            # Check if output contains version information
            if "Version" in result.stdout:
                logger.info(f"Unbound version: {result.stdout.strip()}")
                return True
            
            logger.error(f"Unexpected unbound-control output: {result.stdout}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("unbound-control command timed out")
            return False
        except Exception as e:
            logger.error(f"Error checking unbound-control availability: {e}")
            return False
    
    def _run_unbound_control(self, command: List[str]) -> Tuple[bool, str]:
        """
        Run an unbound-control command.
        
        Args:
            command: Command arguments to pass to unbound-control
            
        Returns:
            Tuple of (success, output)
        """
        try:
            # Construct full command
            full_command = [self.control_path] + command
            
            # Run command
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Check if command succeeded
            if result.returncode != 0:
                logger.error(f"Error running unbound-control {command}: {result.stderr}")
                return False, result.stderr
            
            return True, result.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"unbound-control {command} command timed out")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Error running unbound-control {command}: {e}")
            return False, str(e)
    
    def _get_stats(self) -> Dict[str, Any]:
        """
        Get Unbound statistics.
        
        Returns:
            Dictionary with Unbound statistics
        """
        if not self.available:
            return {"error": "unbound-control is not available"}
        
        success, output = self._run_unbound_control(["stats"])
        if not success:
            return {"error": output}
        
        # Parse statistics
        stats = {}
        for line in output.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            try:
                # Try to convert to appropriate type
                if "." in value:
                    stats[key] = float(value)
                else:
                    stats[key] = int(value)
            except ValueError:
                stats[key] = value
        
        return stats
    
    def _get_status(self) -> Dict[str, Any]:
        """
        Get Unbound server status.
        
        Returns:
            Dictionary with Unbound status
        """
        if not self.available:
            return {"error": "unbound-control is not available"}
        
        success, output = self._run_unbound_control(["status"])
        if not success:
            return {"error": output}
        
        # Parse status
        status = {}
        current_section = "general"
        status[current_section] = {}
        
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # Check for section header
            if line.endswith(":"):
                current_section = line[:-1].lower()
                status[current_section] = {}
                continue
            
            # Parse key-value pair
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                # Try to convert to appropriate type
                try:
                    if value.lower() == "yes":
                        value = True
                    elif value.lower() == "no":
                        value = False
                    elif "." in value and all(c.isdigit() or c == "." for c in value):
                        value = float(value)
                    elif value.isdigit():
                        value = int(value)
                except ValueError:
                    pass
                
                status[current_section][key] = value
        
        return status
    
    def _get_cache_stats(self) -> Dict[str, int]:
        """
        Extract cache statistics from general stats.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = self._get_stats()
        
        if "error" in stats:
            return {"error": stats["error"]}
        
        # Extract cache-related metrics
        cache_stats = {
            "cache_hits": stats.get("total.num.cachehits", 0),
            "cache_misses": stats.get("total.num.cachemiss", 0),
            "prefetch_count": stats.get("total.num.prefetch", 0),
            "zero_ttl_count": stats.get("total.num.zero_ttl", 0),
            "recursive_replies": stats.get("total.num.recursivereplies", 0)
        }
        
        return cache_stats
    
    def _get_query_stats(self) -> Dict[str, int]:
        """
        Extract query statistics from general stats.
        
        Returns:
            Dictionary with query statistics
        """
        stats = self._get_stats()
        
        if "error" in stats:
            return {"error": stats["error"]}
        
        # Extract query-related metrics
        query_stats = {
            "total_queries": stats.get("total.num.queries", 0),
            "queries_ip4": stats.get("total.num.queries_ip4", 0),
            "queries_ip6": stats.get("total.num.queries_ip6", 0),
            "queries_tcp": stats.get("total.num.queries_tcp", 0),
            "queries_udp": stats.get("total.num.queries_udp", 0),
            "queries_tls": stats.get("total.num.queries_tls", 0),
            "queries_https": stats.get("total.num.queries_https", 0)
        }
        
        # Extract query types if available
        for key, value in stats.items():
            if key.startswith("num.query.type."):
                query_type = key.split(".")[-1]
                query_stats[f"query_type_{query_type}"] = value
        
        return query_stats
    
    def _get_memory_stats(self) -> Dict[str, int]:
        """
        Extract memory statistics from general stats.
        
        Returns:
            Dictionary with memory statistics
        """
        stats = self._get_stats()
        
        if "error" in stats:
            return {"error": stats["error"]}
        
        # Extract memory-related metrics
        memory_stats = {
            "memory_cache_rrsets": stats.get("mem.cache.rrset", 0),
            "memory_cache_message": stats.get("mem.cache.message", 0),
            "memory_mod_iterator": stats.get("mem.mod.iterator", 0),
            "memory_mod_validator": stats.get("mem.mod.validator", 0)
        }
        
        return memory_stats
    
    def _flush_cache(self) -> bool:
        """
        Flush the Unbound cache.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.available:
            logger.error("Cannot flush cache: unbound-control is not available")
            return False
        
        success, output = self._run_unbound_control(["flush_zone", "."])
        if not success:
            logger.error(f"Error flushing cache: {output}")
            return False
        
        logger.info("Unbound cache flushed successfully")
        return True
    
    def collect(self) -> Dict[str, Any]:
        """
        Collect Unbound metrics.
        
        Returns:
            Dictionary with collected Unbound data
        """
        logger.debug("Collecting Unbound metrics")
        
        if not self.available:
            return {
                "error": "unbound-control is not available",
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        try:
            # Get current timestamp
            timestamp = datetime.datetime.now().isoformat()
            
            # Get basic statistics
            stats = self._get_stats()
            
            # Check for errors
            if "error" in stats:
                return {
                    "error": stats["error"],
                    "timestamp": timestamp
                }
            
            # Get server status (less frequently)
            status = {}
            if self._last_collection_time == 0 or (
                datetime.datetime.now().minute % 10 == 0
            ):
                status = self._get_status()
            
            # Calculate cache hit rate
            cache_hits = stats.get("total.num.cachehits", 0)
            cache_misses = stats.get("total.num.cachemiss", 0)
            total_queries = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0
            
            # Extract key metrics
            cache_stats = self._get_cache_stats()
            query_stats = self._get_query_stats()
            memory_stats = self._get_memory_stats()
            
            # Combine all data
            data = {
                "timestamp": timestamp,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "prefetch_count": stats.get("total.num.prefetch", 0),
                "total_queries": stats.get("total.num.queries", 0),
                "cache_stats": cache_stats,
                "query_stats": query_stats,
                "memory_stats": memory_stats,
                "status": status
            }
            
            return data
        except Exception as e:
            logger.error(f"Error collecting Unbound data: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        Store the collected Unbound data in InfluxDB.
        
        Args:
            data: The collected Unbound data
        """
        # Don't store if there was an error
        if "error" in data:
            logger.error(f"Not storing Unbound data due to collection error: {data['error']}")
            return
        
        timestamp = data.get("timestamp")
        if not timestamp:
            timestamp = datetime.datetime.now().isoformat()
        
        try:
            # Store core metrics in InfluxDB
            self.influx_db.write_unbound_metrics(
                cache_hits=data.get("cache_hits", 0),
                cache_misses=data.get("cache_misses", 0),
                prefetch_count=data.get("prefetch_count", 0),
                timestamp=timestamp
            )
            
            logger.debug("Stored Unbound metrics in InfluxDB")
        except Exception as e:
            logger.error(f"Error storing Unbound data: {e}")
    
    def flush_cache(self) -> bool:
        """
        Flush the Unbound cache.
        
        Returns:
            True if successful, False otherwise
        """
        return self._flush_cache() 