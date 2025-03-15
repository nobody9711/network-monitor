"""
Pi-hole Integration - Collects metrics from Pi-hole DNS server
"""

import logging
import datetime
import json
from typing import Dict, Any, Optional, List

import requests

from src.collectors.base import BaseCollector
from src.database.influx import InfluxDBStorage
from src.database.mongo import MongoDBStorage

logger = logging.getLogger(__name__)

class PiholeCollector(BaseCollector):
    """
    Collector for Pi-hole metrics.
    
    Retrieves statistics and metrics from Pi-hole DNS server
    using its API.
    """
    
    def __init__(self, api_url: str, api_key: Optional[str], 
                influx_db: InfluxDBStorage, mongo_db: MongoDBStorage,
                interval: int = 10):
        """
        Initialize the Pi-hole collector.
        
        Args:
            api_url: URL of the Pi-hole API
            api_key: API key for accessing the Pi-hole API (optional)
            influx_db: InfluxDB storage instance
            mongo_db: MongoDB storage instance
            interval: Collection interval in seconds
        """
        super().__init__(interval=interval)
        self.api_url = api_url
        self.api_key = api_key
        self.influx_db = influx_db
        self.mongo_db = mongo_db
        
        # Cached data
        self.top_items = {}
        self.forward_destinations = {}
        self.domains_blocked = 0
    
    def _get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics from Pi-hole.
        
        Returns:
            Dictionary with summary statistics
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key if available
            params = {}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            # Parse response
            data = response.json()
            
            # Check for API errors
            if isinstance(data, dict) and "FTLnotrunning" in data:
                logger.error("Pi-hole FTL service is not running")
                return {"error": "Pi-hole FTL service is not running"}
            
            return data
        except requests.RequestException as e:
            logger.error(f"Error requesting Pi-hole API: {e}")
            return {"error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Pi-hole API response: {e}")
            return {"error": f"Invalid JSON response: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error getting Pi-hole stats: {e}")
            return {"error": str(e)}
    
    def _get_query_types(self) -> Dict[str, Any]:
        """
        Get query type distribution from Pi-hole.
        
        Returns:
            Dictionary with query type statistics
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and query type parameter
            params = {"getQueryTypes": ""}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            # Parse response
            data = response.json()
            
            return data
        except Exception as e:
            logger.error(f"Error getting Pi-hole query types: {e}")
            return {"error": str(e)}
    
    def _get_forward_destinations(self) -> Dict[str, Any]:
        """
        Get forwarded DNS destination distribution from Pi-hole.
        
        Returns:
            Dictionary with forward destination statistics
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and forward destinations parameter
            params = {"getForwardDestinations": ""}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            # Parse response
            data = response.json()
            
            # Cache the data
            if isinstance(data, dict) and "forward_destinations" in data:
                self.forward_destinations = data["forward_destinations"]
            
            return data
        except Exception as e:
            logger.error(f"Error getting Pi-hole forward destinations: {e}")
            return {"error": str(e)}
    
    def _get_top_items(self) -> Dict[str, Any]:
        """
        Get top domains and clients from Pi-hole.
        
        Returns:
            Dictionary with top items
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and top items parameter
            params = {"topItems": "25"}  # Get top 25 items
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            # Parse response
            data = response.json()
            
            # Cache the data
            if isinstance(data, dict):
                self.top_items = data
            
            return data
        except Exception as e:
            logger.error(f"Error getting Pi-hole top items: {e}")
            return {"error": str(e)}
    
    def _get_version(self) -> Dict[str, Any]:
        """
        Get Pi-hole version information.
        
        Returns:
            Dictionary with version information
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and version parameter
            params = {"version": ""}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return {"error": f"HTTP error {response.status_code}"}
            
            # Parse response
            data = response.json()
            
            return data
        except Exception as e:
            logger.error(f"Error getting Pi-hole version: {e}")
            return {"error": str(e)}
    
    def collect(self) -> Dict[str, Any]:
        """
        Collect Pi-hole metrics.
        
        Returns:
            Dictionary with collected Pi-hole data
        """
        logger.debug("Collecting Pi-hole metrics")
        
        try:
            # Get current timestamp
            timestamp = datetime.datetime.now().isoformat()
            
            # Get summary statistics
            summary = self._get_summary_stats()
            
            # Check for errors
            if "error" in summary:
                return {
                    "error": summary["error"],
                    "timestamp": timestamp
                }
            
            # Extract key metrics
            dns_queries_today = summary.get("dns_queries_today", 0)
            ads_blocked_today = summary.get("ads_blocked_today", 0)
            ads_percentage_today = summary.get("ads_percentage_today", 0)
            domains_being_blocked = summary.get("domains_being_blocked", 0)
            unique_domains = summary.get("unique_domains", 0)
            queries_forwarded = summary.get("queries_forwarded", 0)
            queries_cached = summary.get("queries_cached", 0)
            clients_ever_seen = summary.get("clients_ever_seen", 0)
            unique_clients = summary.get("unique_clients", 0)
            
            # Get query types (less frequently)
            query_types = {}
            if self._last_collection_time == 0 or (
                datetime.datetime.now().minute % 5 == 0
            ):
                query_types_data = self._get_query_types()
                if "error" not in query_types_data:
                    query_types = query_types_data.get("querytypes", {})
            
            # Get forward destinations (less frequently)
            forward_destinations = {}
            if self._last_collection_time == 0 or (
                datetime.datetime.now().minute % 5 == 0
            ):
                forward_dest_data = self._get_forward_destinations()
                if "error" not in forward_dest_data:
                    forward_destinations = forward_dest_data.get("forward_destinations", {})
                    self.forward_destinations = forward_destinations
            else:
                forward_destinations = self.forward_destinations
            
            # Get top items (less frequently)
            top_items = {}
            if self._last_collection_time == 0 or (
                datetime.datetime.now().minute % 10 == 0
            ):
                top_items_data = self._get_top_items()
                if "error" not in top_items_data:
                    top_items = top_items_data
                    self.top_items = top_items
            else:
                top_items = self.top_items
            
            # Get version info (rarely)
            version_info = {}
            if self._last_collection_time == 0:
                version_data = self._get_version()
                if "error" not in version_data:
                    version_info = version_data
            
            # Update cached domain count
            if domains_being_blocked > 0:
                self.domains_blocked = domains_being_blocked
            
            # Combine all data
            data = {
                "timestamp": timestamp,
                "dns_queries": dns_queries_today,
                "ads_blocked": ads_blocked_today,
                "ads_percentage": ads_percentage_today,
                "domains_blocked": domains_being_blocked or self.domains_blocked,
                "unique_domains": unique_domains,
                "queries_forwarded": queries_forwarded,
                "queries_cached": queries_cached,
                "clients_ever_seen": clients_ever_seen,
                "unique_clients": unique_clients,
                "query_types": query_types,
                "forward_destinations": forward_destinations,
                "top_items": top_items,
                "version": version_info
            }
            
            return data
        except Exception as e:
            logger.error(f"Error collecting Pi-hole data: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        Store the collected Pi-hole data in databases.
        
        Args:
            data: The collected Pi-hole data
        """
        # Don't store if there was an error
        if "error" in data:
            logger.error(f"Not storing Pi-hole data due to collection error: {data['error']}")
            return
        
        timestamp = data.get("timestamp")
        if not timestamp:
            timestamp = datetime.datetime.now().isoformat()
        
        try:
            # Store core metrics in InfluxDB
            self.influx_db.write_pihole_metrics(
                dns_queries=data.get("dns_queries", 0),
                ads_blocked=data.get("ads_blocked", 0),
                domains_blocked=data.get("domains_blocked", 0),
                timestamp=timestamp
            )
            
            # Store detailed data in MongoDB if needed
            # (for things like top domains, clients, etc.)
            if "top_items" in data and data["top_items"]:
                # Create a snapshot record
                self.mongo_db.create_event({
                    "event_type": "pihole_snapshot",
                    "timestamp": timestamp,
                    "severity": "info",
                    "source": "pihole",
                    "data": {
                        "top_domains": data["top_items"].get("top_queries", {}),
                        "top_blocked": data["top_items"].get("top_ads", {}),
                        "top_clients": data["top_items"].get("top_sources", {})
                    }
                })
            
            logger.debug("Stored Pi-hole metrics in databases")
        except Exception as e:
            logger.error(f"Error storing Pi-hole data: {e}")
    
    def enable_pihole(self) -> bool:
        """
        Enable Pi-hole ad blocking.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and enable parameter
            params = {"enable": ""}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return False
            
            # Parse response
            data = response.json()
            
            # Check success
            if "status" in data and data["status"] == "enabled":
                logger.info("Pi-hole ad blocking enabled")
                return True
            
            logger.error(f"Failed to enable Pi-hole: {data}")
            return False
        except Exception as e:
            logger.error(f"Error enabling Pi-hole: {e}")
            return False
    
    def disable_pihole(self, seconds: int = 0) -> bool:
        """
        Disable Pi-hole ad blocking.
        
        Args:
            seconds: Number of seconds to disable (0 = indefinitely)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build API URL
            url = self.api_url
            
            # Add API key and disable parameter
            params = {"disable": str(seconds)}
            if self.api_key:
                params["auth"] = self.api_key
            
            # Make API request
            response = requests.get(url, params=params, timeout=5)
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Pi-hole API request failed: {response.status_code}")
                return False
            
            # Parse response
            data = response.json()
            
            # Check success
            if "status" in data and data["status"] == "disabled":
                if seconds > 0:
                    logger.info(f"Pi-hole ad blocking disabled for {seconds} seconds")
                else:
                    logger.info("Pi-hole ad blocking disabled indefinitely")
                return True
            
            logger.error(f"Failed to disable Pi-hole: {data}")
            return False
        except Exception as e:
            logger.error(f"Error disabling Pi-hole: {e}")
            return False 