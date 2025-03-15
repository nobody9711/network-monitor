"""
Network Monitor Manager - Core coordination for the Network Monitor application.
Manages all collectors, processors, and data storage.
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional
import schedule

from src.core.config import Config
from src.database.influx import InfluxDBStorage
from src.database.mongo import MongoDBStorage
from src.collectors.bandwidth import BandwidthCollector
from src.collectors.devices import DeviceCollector
from src.collectors.performance import PerformanceCollector
from src.collectors.security import SecurityCollector
from src.integrations.pihole.collector import PiholeCollector
from src.integrations.unbound.collector import UnboundCollector
from src.security.analyzer import SecurityAnalyzer
from src.security.alerts import AlertManager

logger = logging.getLogger(__name__)

class NetworkMonitorManager:
    """
    Central manager for all Network Monitor components.
    
    Coordinates data collection, processing, storage, and retrieval.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the Network Monitor Manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.running = False
        self._collectors = {}
        self._storage = {}
        self._analyzers = {}
        
        # Initialize storage backends
        self._init_storage()
        
        # Initialize data collectors
        self._init_collectors()
        
        # Initialize security analyzers
        self._init_analyzers()
        
        # Initialize alert manager
        self.alert_manager = AlertManager(config)
        
        # Create scheduler for periodic tasks
        self.scheduler = schedule.Scheduler()
        
        logger.info("Network Monitor Manager initialized")
    
    def _init_storage(self):
        """Initialize all storage backends."""
        # Set up InfluxDB for time-series metrics
        self._storage['influx'] = InfluxDBStorage(
            url=self.config.influxdb_url,
            token=self.config.influxdb_token,
            org=self.config.influxdb_org,
            bucket=self.config.influxdb_bucket
        )
        
        # Set up MongoDB for device data, events, and configuration
        self._storage['mongo'] = MongoDBStorage(
            uri=self.config.mongodb_uri,
            database=self.config.mongodb_db
        )
        
        logger.debug("Storage backends initialized")
    
    def _init_collectors(self):
        """Initialize all data collectors."""
        # Bandwidth usage collector
        self._collectors['bandwidth'] = BandwidthCollector(
            interface=self.config.network_interface,
            influx_db=self._storage['influx'],
            interval=self.config.bandwidth_interval
        )
        
        # Device discovery and tracking
        self._collectors['devices'] = DeviceCollector(
            interface=self.config.network_interface,
            mongo_db=self._storage['mongo'],
            interval=self.config.device_scan_interval
        )
        
        # System performance metrics
        self._collectors['performance'] = PerformanceCollector(
            influx_db=self._storage['influx'],
            interval=self.config.performance_interval
        )
        
        # Security scanning
        if self.config.enable_security_scanning:
            self._collectors['security'] = SecurityCollector(
                interface=self.config.network_interface,
                mongo_db=self._storage['mongo'],
                influx_db=self._storage['influx'],
                interval=self.config.security_scan_interval
            )
        
        # Pi-hole integration
        if self.config.pihole_enabled:
            self._collectors['pihole'] = PiholeCollector(
                api_url=self.config.pihole_api_url,
                api_key=self.config.pihole_api_key,
                influx_db=self._storage['influx'],
                mongo_db=self._storage['mongo'],
                interval=self.config.bandwidth_interval
            )
        
        # Unbound integration
        if self.config.unbound_enabled:
            self._collectors['unbound'] = UnboundCollector(
                control_path=self.config.unbound_control_path,
                influx_db=self._storage['influx'],
                interval=self.config.bandwidth_interval
            )
        
        logger.debug(f"Initialized {len(self._collectors)} data collectors")
    
    def _init_analyzers(self):
        """Initialize security analyzers."""
        if self.config.enable_security_scanning:
            self._analyzers['security'] = SecurityAnalyzer(
                mongo_db=self._storage['mongo'],
                influx_db=self._storage['influx'],
                alert_manager=self.alert_manager,
                bandwidth_threshold=self.config.bandwidth_alert_threshold,
                cpu_threshold=self.config.cpu_alert_threshold
            )
            logger.debug("Security analyzer initialized")
    
    def _setup_schedules(self):
        """Set up scheduled tasks."""
        # Cleanup old data
        self.scheduler.every().day.at("01:00").do(self._cleanup_old_data)
        
        # Run security analysis
        if self.config.enable_security_scanning:
            self.scheduler.every(30).minutes.do(self._run_security_analysis)
        
        logger.debug("Scheduled tasks set up")
    
    def _cleanup_old_data(self):
        """Clean up old data based on retention policies."""
        logger.info("Running scheduled data cleanup")
        try:
            # Clean up old metrics
            self._storage['influx'].delete_old_data(self.config.metrics_retention_days)
            
            # Clean up old events
            self._storage['mongo'].delete_old_events(self.config.events_retention_days)
            
            logger.info("Data cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")
    
    def _run_security_analysis(self):
        """Run the security analysis."""
        logger.info("Running scheduled security analysis")
        try:
            self._analyzers['security'].analyze()
            logger.info("Security analysis completed")
        except Exception as e:
            logger.error(f"Error during security analysis: {e}")
    
    def _scheduler_thread(self):
        """Thread function for running the scheduler."""
        logger.debug("Scheduler thread started")
        while self.running:
            self.scheduler.run_pending()
            time.sleep(1)
    
    def start(self):
        """Start all collectors and monitoring."""
        if self.running:
            logger.warning("Network Monitor Manager is already running")
            return
        
        logger.info("Starting Network Monitor Manager")
        
        # Mark as running
        self.running = True
        
        # Set up scheduled tasks
        self._setup_schedules()
        
        # Start the scheduler in a separate thread
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_thread,
            daemon=True
        )
        self.scheduler_thread.start()
        
        # Start all collectors
        for name, collector in self._collectors.items():
            try:
                collector.start()
                logger.info(f"Started {name} collector")
            except Exception as e:
                logger.error(f"Failed to start {name} collector: {e}")
        
        logger.info("Network Monitor Manager started successfully")
    
    def stop(self):
        """Stop all collectors and monitoring."""
        if not self.running:
            logger.warning("Network Monitor Manager is not running")
            return
        
        logger.info("Stopping Network Monitor Manager")
        
        # Mark as not running
        self.running = False
        
        # Stop all collectors
        for name, collector in self._collectors.items():
            try:
                collector.stop()
                logger.info(f"Stopped {name} collector")
            except Exception as e:
                logger.error(f"Failed to stop {name} collector: {e}")
        
        # Wait for scheduler thread to finish
        if hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5.0)
        
        logger.info("Network Monitor Manager stopped successfully")
    
    def get_device_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all detected devices.
        
        Returns:
            List of device dictionaries with details
        """
        return self._storage['mongo'].get_all_devices()
    
    def get_bandwidth_metrics(self, start_time: Optional[str] = None, 
                             end_time: Optional[str] = None,
                             device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get bandwidth metrics for the specified time range.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            device_id: Filter by device ID (optional)
            
        Returns:
            List of bandwidth metrics
        """
        return self._storage['influx'].get_bandwidth_metrics(
            start_time=start_time,
            end_time=end_time,
            device_id=device_id
        )
    
    def get_performance_metrics(self, start_time: Optional[str] = None,
                               end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get system performance metrics for the specified time range.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            List of performance metrics
        """
        return self._storage['influx'].get_performance_metrics(
            start_time=start_time,
            end_time=end_time
        )
    
    def get_security_events(self, start_time: Optional[str] = None,
                          end_time: Optional[str] = None,
                          severity: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get security events for the specified time range.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            severity: Filter by severity (high, medium, low)
            limit: Maximum number of events to return
            
        Returns:
            List of security events
        """
        return self._storage['mongo'].get_security_events(
            start_time=start_time,
            end_time=end_time,
            severity=severity,
            limit=limit
        )
    
    def get_pihole_stats(self, start_time: Optional[str] = None,
                       end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Pi-hole statistics for the specified time range.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            Dictionary of Pi-hole statistics
        """
        if not self.config.pihole_enabled:
            return {"error": "Pi-hole integration is disabled"}
        
        return self._storage['influx'].get_pihole_stats(
            start_time=start_time,
            end_time=end_time
        )
    
    def get_unbound_stats(self, start_time: Optional[str] = None,
                        end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Unbound statistics for the specified time range.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            Dictionary of Unbound statistics
        """
        if not self.config.unbound_enabled:
            return {"error": "Unbound integration is disabled"}
        
        return self._storage['influx'].get_unbound_stats(
            start_time=start_time,
            end_time=end_time
        )
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the dashboard.
        
        Returns:
            Dictionary of summary statistics
        """
        # Get device count
        device_count = len(self._storage['mongo'].get_all_devices())
        
        # Get recent bandwidth usage
        recent_bandwidth = self._storage['influx'].get_recent_bandwidth()
        
        # Get recent performance metrics
        recent_performance = self._storage['influx'].get_recent_performance()
        
        # Get recent security events
        recent_events = self._storage['mongo'].get_security_events(limit=5)
        
        # Get pi-hole summary if enabled
        pihole_summary = {}
        if self.config.pihole_enabled:
            pihole_summary = self._storage['influx'].get_pihole_summary()
        
        return {
            "device_count": device_count,
            "bandwidth": recent_bandwidth,
            "performance": recent_performance,
            "recent_events": recent_events,
            "pihole": pihole_summary
        } 