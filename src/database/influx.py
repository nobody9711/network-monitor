"""
InfluxDB Storage - Database access for time-series metrics
"""

import logging
import datetime
from typing import Dict, Any, List, Optional, Union
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.flux_table import FluxTable

logger = logging.getLogger(__name__)

class InfluxDBStorage:
    """
    InfluxDB storage adapter for Network Monitor.
    
    Handles storing and retrieving time-series metrics for
    bandwidth, connections, device activity, and system performance.
    """
    
    def __init__(self, url: str, token: str, org: str, bucket: str):
        """
        Initialize the InfluxDB storage adapter.
        
        Args:
            url: InfluxDB server URL
            token: API token
            org: Organization name
            bucket: Bucket name
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        self.write_api = None
        self.query_api = None
        
        # Connect to InfluxDB
        self._connect()
    
    def _connect(self) -> None:
        """Connect to InfluxDB and set up APIs."""
        try:
            logger.debug(f"Connecting to InfluxDB at {self.url}")
            self.client = influxdb_client.InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            
            # Set up write API
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            
            # Set up query API
            self.query_api = self.client.query_api()
            
            # Check connection
            health = self.client.health()
            if health.status == "pass":
                logger.info("Connected to InfluxDB successfully")
            else:
                logger.warning(f"InfluxDB health check: {health.status}")
            
            # Create the bucket if it doesn't exist
            buckets_api = self.client.buckets_api()
            existing_buckets = [b.name for b in buckets_api.find_buckets().buckets]
            
            if self.bucket not in existing_buckets:
                logger.info(f"Creating bucket '{self.bucket}'")
                organization = self.client.organizations_api().find_organizations(org=self.org)[0]
                buckets_api.create_bucket(bucket_name=self.bucket, org_id=organization.id)
        except Exception as e:
            logger.error(f"Error connecting to InfluxDB: {e}")
            raise
    
    def close(self) -> None:
        """Close the InfluxDB connection."""
        if self.client:
            self.client.close()
            logger.debug("InfluxDB connection closed")
    
    # Write methods
    
    def write_bandwidth_metrics(self, upload_bps: float, download_bps: float, 
                               total_bps: float, upload_bytes: int, 
                               download_bytes: int, timestamp: str) -> None:
        """
        Write bandwidth metrics to InfluxDB.
        
        Args:
            upload_bps: Upload bandwidth in bits per second
            download_bps: Download bandwidth in bits per second
            total_bps: Total bandwidth in bits per second
            upload_bytes: Bytes uploaded in the interval
            download_bytes: Bytes downloaded in the interval
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("bandwidth")\
                .tag("metric_type", "network")\
                .field("upload_bps", float(upload_bps))\
                .field("download_bps", float(download_bps))\
                .field("total_bps", float(total_bps))\
                .field("upload_bytes", int(upload_bytes))\
                .field("download_bytes", int(download_bytes))\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote bandwidth metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing bandwidth metrics to InfluxDB: {e}")
    
    def write_connection_metrics(self, connection_count: int, timestamp: str) -> None:
        """
        Write connection metrics to InfluxDB.
        
        Args:
            connection_count: Number of active connections
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("connections")\
                .tag("metric_type", "network")\
                .field("connection_count", int(connection_count))\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote connection metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing connection metrics to InfluxDB: {e}")
    
    def write_protocol_metrics(self, protocol: str, count: int, timestamp: str) -> None:
        """
        Write protocol distribution metrics to InfluxDB.
        
        Args:
            protocol: Protocol name (e.g., TCP, UDP)
            count: Number of packets
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("protocols")\
                .tag("metric_type", "network")\
                .tag("protocol", protocol)\
                .field("count", int(count))\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug(f"Wrote protocol metrics for {protocol} to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing protocol metrics to InfluxDB: {e}")
    
    def write_speedtest_metrics(self, download_mbps: float, upload_mbps: float,
                              ping_ms: float, server: str, timestamp: str) -> None:
        """
        Write speed test results to InfluxDB.
        
        Args:
            download_mbps: Download speed in Mbps
            upload_mbps: Upload speed in Mbps
            ping_ms: Ping time in milliseconds
            server: Speed test server name
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("speedtest")\
                .tag("metric_type", "network")\
                .tag("server", server)\
                .field("download_mbps", float(download_mbps))\
                .field("upload_mbps", float(upload_mbps))\
                .field("ping_ms", float(ping_ms))\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote speed test metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing speed test metrics to InfluxDB: {e}")
    
    def write_performance_metrics(self, cpu_percent: float, memory_percent: float,
                                disk_percent: float, temperature: Optional[float],
                                timestamp: str) -> None:
        """
        Write system performance metrics to InfluxDB.
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
            disk_percent: Disk usage percentage
            temperature: CPU temperature in Celsius (optional)
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("performance")\
                .tag("metric_type", "system")\
                .field("cpu_percent", float(cpu_percent))\
                .field("memory_percent", float(memory_percent))\
                .field("disk_percent", float(disk_percent))\
                .time(timestamp)
            
            # Add temperature if available
            if temperature is not None:
                point = point.field("temperature", float(temperature))
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote performance metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing performance metrics to InfluxDB: {e}")
    
    def write_device_activity(self, mac: str, ip: str, hostname: str,
                             device_type: str, timestamp: str) -> None:
        """
        Write device activity to InfluxDB.
        
        Args:
            mac: Device MAC address
            ip: Device IP address
            hostname: Device hostname
            device_type: Device type
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("device_activity")\
                .tag("metric_type", "device")\
                .tag("mac", mac)\
                .tag("ip", ip)\
                .tag("hostname", hostname or "unknown")\
                .tag("device_type", device_type or "unknown")\
                .field("active", 1)\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug(f"Wrote activity for device {mac} to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing device activity to InfluxDB: {e}")
    
    def write_pihole_metrics(self, dns_queries: int, ads_blocked: int,
                           domains_blocked: int, timestamp: str) -> None:
        """
        Write Pi-hole metrics to InfluxDB.
        
        Args:
            dns_queries: Number of DNS queries
            ads_blocked: Number of ads blocked
            domains_blocked: Number of domains in blocklist
            timestamp: Timestamp in ISO format
        """
        try:
            # Format for InfluxDB
            point = influxdb_client.Point("pihole")\
                .tag("metric_type", "dns")\
                .field("dns_queries", int(dns_queries))\
                .field("ads_blocked", int(ads_blocked))\
                .field("domains_blocked", int(domains_blocked))\
                .field("blocked_percent", float(ads_blocked) / float(dns_queries) * 100 if dns_queries > 0 else 0)\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote Pi-hole metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing Pi-hole metrics to InfluxDB: {e}")
    
    def write_unbound_metrics(self, cache_hits: int, cache_misses: int,
                            prefetch_count: int, timestamp: str) -> None:
        """
        Write Unbound metrics to InfluxDB.
        
        Args:
            cache_hits: Number of cache hits
            cache_misses: Number of cache misses
            prefetch_count: Number of prefetches
            timestamp: Timestamp in ISO format
        """
        try:
            # Calculate cache hit rate
            total_queries = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0
            
            # Format for InfluxDB
            point = influxdb_client.Point("unbound")\
                .tag("metric_type", "dns")\
                .field("cache_hits", int(cache_hits))\
                .field("cache_misses", int(cache_misses))\
                .field("prefetch_count", int(prefetch_count))\
                .field("cache_hit_rate", float(cache_hit_rate))\
                .time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Wrote Unbound metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing Unbound metrics to InfluxDB: {e}")
    
    def write_security_event(self, event_type: str, severity: str,
                           details: Dict[str, Any], timestamp: str) -> None:
        """
        Write security event to InfluxDB.
        
        Args:
            event_type: Type of security event
            severity: Severity level (high, medium, low)
            details: Event details
            timestamp: Timestamp in ISO format
        """
        try:
            # Convert severity to numeric value for easier querying
            severity_value = {"high": 3, "medium": 2, "low": 1}.get(severity.lower(), 1)
            
            # Format for InfluxDB
            point = influxdb_client.Point("security_events")\
                .tag("metric_type", "security")\
                .tag("event_type", event_type)\
                .tag("severity", severity)\
                .field("severity_value", severity_value)\
                .field("event_count", 1)
            
            # Add details as fields
            for key, value in details.items():
                if isinstance(value, (int, float, bool, str)):
                    point = point.field(key, value)
            
            point = point.time(timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug(f"Wrote security event ({event_type}) to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing security event to InfluxDB: {e}")
    
    # Query methods
    
    def get_bandwidth_metrics(self, start_time: Optional[str] = None,
                             end_time: Optional[str] = None,
                             device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get bandwidth metrics for the specified time range.
        
        Args:
            start_time: Start time in ISO format (default: 24 hours ago)
            end_time: End time in ISO format (default: now)
            device_id: Filter by device ID (optional)
            
        Returns:
            List of bandwidth metrics
        """
        try:
            # Set default time range if not specified
            if not start_time:
                start_time = (datetime.datetime.now() - 
                             datetime.timedelta(hours=24)).isoformat()
            if not end_time:
                end_time = datetime.datetime.now().isoformat()
            
            # Build query
            if device_id:
                query = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: {start_time}, stop: {end_time})
                    |> filter(fn: (r) => r._measurement == "device_bandwidth")
                    |> filter(fn: (r) => r.device_id == "{device_id}")
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: false)
                '''
            else:
                query = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: {start_time}, stop: {end_time})
                    |> filter(fn: (r) => r._measurement == "bandwidth")
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: false)
                '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Convert to list of dictionaries
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "upload_bps": record.get_value().get("upload_bps", 0),
                        "download_bps": record.get_value().get("download_bps", 0),
                        "total_bps": record.get_value().get("total_bps", 0)
                    })
            
            return results
        except Exception as e:
            logger.error(f"Error getting bandwidth metrics: {e}")
            return []
    
    def get_performance_metrics(self, start_time: Optional[str] = None,
                              end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get system performance metrics for the specified time range.
        
        Args:
            start_time: Start time in ISO format (default: 24 hours ago)
            end_time: End time in ISO format (default: now)
            
        Returns:
            List of performance metrics
        """
        try:
            # Set default time range if not specified
            if not start_time:
                start_time = (datetime.datetime.now() - 
                             datetime.timedelta(hours=24)).isoformat()
            if not end_time:
                end_time = datetime.datetime.now().isoformat()
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time}, stop: {end_time})
                |> filter(fn: (r) => r._measurement == "performance")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Convert to list of dictionaries
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "cpu_percent": record.get_value().get("cpu_percent", 0),
                        "memory_percent": record.get_value().get("memory_percent", 0),
                        "disk_percent": record.get_value().get("disk_percent", 0),
                        "temperature": record.get_value().get("temperature")
                    })
            
            return results
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return []
    
    def get_pihole_stats(self, start_time: Optional[str] = None,
                       end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Pi-hole statistics for the specified time range.
        
        Args:
            start_time: Start time in ISO format (default: 24 hours ago)
            end_time: End time in ISO format (default: now)
            
        Returns:
            Dictionary of Pi-hole statistics
        """
        try:
            # Set default time range if not specified
            if not start_time:
                start_time = (datetime.datetime.now() - 
                             datetime.timedelta(hours=24)).isoformat()
            if not end_time:
                end_time = datetime.datetime.now().isoformat()
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time}, stop: {end_time})
                |> filter(fn: (r) => r._measurement == "pihole")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Process results
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "dns_queries": record.get_value().get("dns_queries", 0),
                        "ads_blocked": record.get_value().get("ads_blocked", 0),
                        "domains_blocked": record.get_value().get("domains_blocked", 0),
                        "blocked_percent": record.get_value().get("blocked_percent", 0)
                    })
            
            # Calculate summary statistics
            if results:
                # Total DNS queries
                total_queries = sum(r["dns_queries"] for r in results)
                
                # Total ads blocked
                total_blocked = sum(r["ads_blocked"] for r in results)
                
                # Average blocked percentage
                avg_blocked_percent = sum(r["blocked_percent"] for r in results) / len(results)
                
                # Latest domains on blocklist
                latest_domains_blocked = results[-1]["domains_blocked"]
                
                return {
                    "total_queries": total_queries,
                    "total_blocked": total_blocked,
                    "avg_blocked_percent": avg_blocked_percent,
                    "domains_blocked": latest_domains_blocked,
                    "data_points": results
                }
            else:
                return {
                    "total_queries": 0,
                    "total_blocked": 0,
                    "avg_blocked_percent": 0,
                    "domains_blocked": 0,
                    "data_points": []
                }
        except Exception as e:
            logger.error(f"Error getting Pi-hole stats: {e}")
            return {
                "error": str(e),
                "total_queries": 0,
                "total_blocked": 0,
                "avg_blocked_percent": 0,
                "domains_blocked": 0,
                "data_points": []
            }
    
    def get_unbound_stats(self, start_time: Optional[str] = None,
                        end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Unbound statistics for the specified time range.
        
        Args:
            start_time: Start time in ISO format (default: 24 hours ago)
            end_time: End time in ISO format (default: now)
            
        Returns:
            Dictionary of Unbound statistics
        """
        try:
            # Set default time range if not specified
            if not start_time:
                start_time = (datetime.datetime.now() - 
                             datetime.timedelta(hours=24)).isoformat()
            if not end_time:
                end_time = datetime.datetime.now().isoformat()
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time}, stop: {end_time})
                |> filter(fn: (r) => r._measurement == "unbound")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Process results
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "cache_hits": record.get_value().get("cache_hits", 0),
                        "cache_misses": record.get_value().get("cache_misses", 0),
                        "prefetch_count": record.get_value().get("prefetch_count", 0),
                        "cache_hit_rate": record.get_value().get("cache_hit_rate", 0)
                    })
            
            # Calculate summary statistics
            if results:
                # Total cache hits and misses
                total_hits = sum(r["cache_hits"] for r in results)
                total_misses = sum(r["cache_misses"] for r in results)
                
                # Overall cache hit rate
                total_queries = total_hits + total_misses
                overall_hit_rate = (total_hits / total_queries * 100) if total_queries > 0 else 0
                
                # Total prefetches
                total_prefetches = sum(r["prefetch_count"] for r in results)
                
                return {
                    "total_hits": total_hits,
                    "total_misses": total_misses,
                    "overall_hit_rate": overall_hit_rate,
                    "total_prefetches": total_prefetches,
                    "data_points": results
                }
            else:
                return {
                    "total_hits": 0,
                    "total_misses": 0,
                    "overall_hit_rate": 0,
                    "total_prefetches": 0,
                    "data_points": []
                }
        except Exception as e:
            logger.error(f"Error getting Unbound stats: {e}")
            return {
                "error": str(e),
                "total_hits": 0,
                "total_misses": 0,
                "overall_hit_rate": 0,
                "total_prefetches": 0,
                "data_points": []
            }
    
    def get_recent_bandwidth(self, minutes: int = 5) -> Dict[str, Any]:
        """
        Get recent bandwidth metrics.
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            Dictionary with recent bandwidth metrics
        """
        try:
            # Calculate start time
            start_time = (datetime.datetime.now() - 
                         datetime.timedelta(minutes=minutes)).isoformat()
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time})
                |> filter(fn: (r) => r._measurement == "bandwidth")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Get the most recent record
            for table in tables:
                for record in table.records:
                    return {
                        "time": record.get_time().isoformat(),
                        "upload_bps": record.get_value().get("upload_bps", 0),
                        "download_bps": record.get_value().get("download_bps", 0),
                        "total_bps": record.get_value().get("total_bps", 0)
                    }
            
            # No data found
            return {
                "upload_bps": 0,
                "download_bps": 0,
                "total_bps": 0
            }
        except Exception as e:
            logger.error(f"Error getting recent bandwidth: {e}")
            return {
                "error": str(e),
                "upload_bps": 0,
                "download_bps": 0,
                "total_bps": 0
            }
    
    def get_recent_performance(self, minutes: int = 5) -> Dict[str, Any]:
        """
        Get recent performance metrics.
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            Dictionary with recent performance metrics
        """
        try:
            # Calculate start time
            start_time = (datetime.datetime.now() - 
                         datetime.timedelta(minutes=minutes)).isoformat()
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time})
                |> filter(fn: (r) => r._measurement == "performance")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=self.org)
            
            # Get the most recent record
            for table in tables:
                for record in table.records:
                    return {
                        "time": record.get_time().isoformat(),
                        "cpu_percent": record.get_value().get("cpu_percent", 0),
                        "memory_percent": record.get_value().get("memory_percent", 0),
                        "disk_percent": record.get_value().get("disk_percent", 0),
                        "temperature": record.get_value().get("temperature")
                    }
            
            # No data found
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0
            }
        except Exception as e:
            logger.error(f"Error getting recent performance: {e}")
            return {
                "error": str(e),
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0
            }
    
    def get_pihole_summary(self) -> Dict[str, Any]:
        """
        Get Pi-hole summary statistics for the dashboard.
        
        Returns:
            Dictionary with Pi-hole summary statistics
        """
        try:
            # Get stats for the last 24 hours
            start_time = (datetime.datetime.now() - 
                         datetime.timedelta(hours=24)).isoformat()
            
            stats = self.get_pihole_stats(start_time=start_time)
            
            # Calculate stats
            if "error" in stats:
                return {
                    "error": stats["error"],
                    "dns_queries_today": 0,
                    "ads_blocked_today": 0,
                    "ads_percentage_today": 0,
                    "domains_being_blocked": 0
                }
            
            return {
                "dns_queries_today": stats["total_queries"],
                "ads_blocked_today": stats["total_blocked"],
                "ads_percentage_today": stats["avg_blocked_percent"],
                "domains_being_blocked": stats["domains_blocked"]
            }
        except Exception as e:
            logger.error(f"Error getting Pi-hole summary: {e}")
            return {
                "error": str(e),
                "dns_queries_today": 0,
                "ads_blocked_today": 0,
                "ads_percentage_today": 0,
                "domains_being_blocked": 0
            }
    
    def delete_old_data(self, days: int = 30) -> bool:
        """
        Delete data older than the specified number of days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            cutoff_timestamp = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Create delete API
            delete_api = self.client.delete_api()
            
            # Delete old data
            delete_api.delete(
                start=datetime.datetime(2000, 1, 1).strftime("%Y-%m-%dT%H:%M:%SZ"),
                stop=cutoff_timestamp,
                bucket=self.bucket,
                org=self.org,
                predicate="_measurement != \"\"")
            
            logger.info(f"Deleted data older than {days} days")
            return True
        except Exception as e:
            logger.error(f"Error deleting old data: {e}")
            return False 