"""
MongoDB Storage - Database access for device and event data
"""

import logging
import datetime
from typing import Dict, Any, List, Optional, Union
import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

logger = logging.getLogger(__name__)

class MongoDBStorage:
    """
    MongoDB storage adapter for Network Monitor.
    
    Handles storing device data, security events, and other
    non-time-series data.
    """
    
    def __init__(self, uri: str, database: str):
        """
        Initialize the MongoDB storage adapter.
        
        Args:
            uri: MongoDB connection URI
            database: Database name
        """
        self.uri = uri
        self.database_name = database
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        
        # Collections
        self.devices: Optional[Collection] = None
        self.events: Optional[Collection] = None
        self.settings: Optional[Collection] = None
        
        # Connect to the database
        self._connect()
        
        # Set up indices
        self._setup_indices()
    
    def _connect(self) -> None:
        """Connect to MongoDB and set up collections."""
        try:
            logger.debug(f"Connecting to MongoDB at {self.uri}")
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
            
            # Set up collections
            self.devices = self.db.devices
            self.events = self.db.events
            self.settings = self.db.settings
            
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise
    
    def _setup_indices(self) -> None:
        """Set up indices for better query performance."""
        try:
            # Device collection indices
            self.devices.create_index([("mac", pymongo.ASCENDING)], unique=True)
            self.devices.create_index([("ip", pymongo.ASCENDING)])
            self.devices.create_index([("hostname", pymongo.ASCENDING)])
            self.devices.create_index([("vendor", pymongo.ASCENDING)])
            self.devices.create_index([("device_type", pymongo.ASCENDING)])
            self.devices.create_index([("last_seen", pymongo.DESCENDING)])
            
            # Events collection indices
            self.events.create_index([("timestamp", pymongo.DESCENDING)])
            self.events.create_index([("event_type", pymongo.ASCENDING)])
            self.events.create_index([("severity", pymongo.ASCENDING)])
            self.events.create_index([("source_ip", pymongo.ASCENDING)])
            self.events.create_index([("target_ip", pymongo.ASCENDING)])
            
            logger.debug("MongoDB indices set up successfully")
        except Exception as e:
            logger.error(f"Error setting up MongoDB indices: {e}")
    
    def close(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.debug("MongoDB connection closed")
    
    # Device methods
    
    def create_device(self, device_data: Dict[str, Any]) -> str:
        """
        Create a new device record.
        
        Args:
            device_data: Device data to store
            
        Returns:
            ID of the created device
        """
        try:
            # Ensure MAC address is present
            if "mac" not in device_data:
                raise ValueError("Device data must include MAC address")
            
            # Add timestamp if not present
            if "first_seen" not in device_data:
                device_data["first_seen"] = datetime.datetime.now().isoformat()
            if "last_seen" not in device_data:
                device_data["last_seen"] = device_data["first_seen"]
            
            # Insert the device
            result = self.devices.insert_one(device_data)
            
            logger.debug(f"Created device with MAC {device_data['mac']}")
            return str(result.inserted_id)
        except pymongo.errors.DuplicateKeyError:
            # Device already exists, update it instead
            self.update_device(device_data["mac"], device_data)
            logger.debug(f"Device with MAC {device_data['mac']} already exists, updated instead")
            return device_data["mac"]
        except Exception as e:
            logger.error(f"Error creating device: {e}")
            raise
    
    def update_device(self, mac: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing device.
        
        Args:
            mac: MAC address of the device to update
            update_data: Data to update
            
        Returns:
            True if the device was updated, False otherwise
        """
        try:
            # Update the device
            result = self.devices.update_one(
                {"mac": mac},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.debug(f"Updated device with MAC {mac}")
                return True
            else:
                logger.debug(f"No changes for device with MAC {mac}")
                return False
        except Exception as e:
            logger.error(f"Error updating device {mac}: {e}")
            return False
    
    def get_device_by_mac(self, mac: str) -> Optional[Dict[str, Any]]:
        """
        Get a device by MAC address.
        
        Args:
            mac: MAC address of the device
            
        Returns:
            Device data or None if not found
        """
        try:
            device = self.devices.find_one({"mac": mac})
            if device:
                # Convert ObjectId to string for JSON serialization
                device["_id"] = str(device["_id"])
                return device
            return None
        except Exception as e:
            logger.error(f"Error getting device {mac}: {e}")
            return None
    
    def get_device_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Get a device by IP address.
        
        This gets the most recently seen device with the given IP.
        
        Args:
            ip: IP address of the device
            
        Returns:
            Device data or None if not found
        """
        try:
            device = self.devices.find_one(
                {"ip": ip},
                sort=[("last_seen", pymongo.DESCENDING)]
            )
            if device:
                # Convert ObjectId to string for JSON serialization
                device["_id"] = str(device["_id"])
                return device
            return None
        except Exception as e:
            logger.error(f"Error getting device with IP {ip}: {e}")
            return None
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices.
        
        Returns:
            List of all devices
        """
        try:
            devices = list(self.devices.find().sort("last_seen", pymongo.DESCENDING))
            
            # Convert ObjectId to string for JSON serialization
            for device in devices:
                device["_id"] = str(device["_id"])
            
            return devices
        except Exception as e:
            logger.error(f"Error getting all devices: {e}")
            return []
    
    def get_devices_by_type(self, device_type: str) -> List[Dict[str, Any]]:
        """
        Get devices by type.
        
        Args:
            device_type: Type of devices to get
            
        Returns:
            List of devices of the specified type
        """
        try:
            devices = list(self.devices.find(
                {"device_type": device_type}
            ).sort("last_seen", pymongo.DESCENDING))
            
            # Convert ObjectId to string for JSON serialization
            for device in devices:
                device["_id"] = str(device["_id"])
            
            return devices
        except Exception as e:
            logger.error(f"Error getting devices of type {device_type}: {e}")
            return []
    
    def get_active_devices(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get devices that have been active in the last N hours.
        
        Args:
            hours: Number of hours to consider as active
            
        Returns:
            List of active devices
        """
        try:
            # Calculate cutoff time
            cutoff = (datetime.datetime.now() - 
                     datetime.timedelta(hours=hours)).isoformat()
            
            devices = list(self.devices.find(
                {"last_seen": {"$gte": cutoff}}
            ).sort("last_seen", pymongo.DESCENDING))
            
            # Convert ObjectId to string for JSON serialization
            for device in devices:
                device["_id"] = str(device["_id"])
            
            return devices
        except Exception as e:
            logger.error(f"Error getting active devices: {e}")
            return []
    
    def delete_device(self, mac: str) -> bool:
        """
        Delete a device.
        
        Args:
            mac: MAC address of the device to delete
            
        Returns:
            True if the device was deleted, False otherwise
        """
        try:
            result = self.devices.delete_one({"mac": mac})
            
            if result.deleted_count > 0:
                logger.debug(f"Deleted device with MAC {mac}")
                return True
            else:
                logger.debug(f"No device found with MAC {mac}")
                return False
        except Exception as e:
            logger.error(f"Error deleting device {mac}: {e}")
            return False
    
    # Event methods
    
    def create_event(self, event_data: Dict[str, Any]) -> str:
        """
        Create a new security event.
        
        Args:
            event_data: Event data to store
            
        Returns:
            ID of the created event
        """
        try:
            # Add timestamp if not present
            if "timestamp" not in event_data:
                event_data["timestamp"] = datetime.datetime.now().isoformat()
            
            # Insert the event
            result = self.events.insert_one(event_data)
            
            logger.debug(f"Created event: {event_data.get('event_type', 'unknown')}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise
    
    def get_security_events(self, start_time: Optional[str] = None, 
                           end_time: Optional[str] = None,
                           event_type: Optional[str] = None,
                           severity: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get security events with optional filtering.
        
        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            event_type: Filter by event type
            severity: Filter by severity
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        try:
            # Build query
            query = {}
            
            if start_time or end_time:
                query["timestamp"] = {}
                if start_time:
                    query["timestamp"]["$gte"] = start_time
                if end_time:
                    query["timestamp"]["$lte"] = end_time
            
            if event_type:
                query["event_type"] = event_type
            
            if severity:
                query["severity"] = severity
            
            # Get events
            events = list(self.events.find(query)
                         .sort("timestamp", pymongo.DESCENDING)
                         .limit(limit))
            
            # Convert ObjectId to string for JSON serialization
            for event in events:
                event["_id"] = str(event["_id"])
            
            return events
        except Exception as e:
            logger.error(f"Error getting security events: {e}")
            return []
    
    def get_events_by_device(self, ip: str, mac: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events for a specific device.
        
        Args:
            ip: IP address of the device
            mac: MAC address of the device (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of events for the device
        """
        try:
            # Build query
            query = {"$or": [{"source_ip": ip}, {"target_ip": ip}]}
            
            if mac:
                query["$or"].append({"source_mac": mac})
                query["$or"].append({"target_mac": mac})
            
            # Get events
            events = list(self.events.find(query)
                         .sort("timestamp", pymongo.DESCENDING)
                         .limit(limit))
            
            # Convert ObjectId to string for JSON serialization
            for event in events:
                event["_id"] = str(event["_id"])
            
            return events
        except Exception as e:
            logger.error(f"Error getting events for device {ip}: {e}")
            return []
    
    def delete_old_events(self, days: int = 90) -> int:
        """
        Delete events older than the specified number of days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of deleted events
        """
        try:
            # Calculate cutoff time
            cutoff = (datetime.datetime.now() - 
                     datetime.timedelta(days=days)).isoformat()
            
            # Delete events
            result = self.events.delete_many(
                {"timestamp": {"$lt": cutoff}}
            )
            
            deleted_count = result.deleted_count
            logger.info(f"Deleted {deleted_count} old events")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting old events: {e}")
            return 0
    
    # Settings methods
    
    def get_setting(self, key: str) -> Optional[Any]:
        """
        Get a setting value.
        
        Args:
            key: Setting key
            
        Returns:
            Setting value or None if not found
        """
        try:
            setting = self.settings.find_one({"key": key})
            if setting:
                return setting["value"]
            return None
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return None
    
    def set_setting(self, key: str, value: Any) -> bool:
        """
        Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if the setting was set, False otherwise
        """
        try:
            # Update or insert the setting
            result = self.settings.update_one(
                {"key": key},
                {"$set": {"value": value}},
                upsert=True
            )
            
            logger.debug(f"Set setting {key} to {value}")
            return True
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False 