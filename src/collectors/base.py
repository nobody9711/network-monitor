"""
Base Collector module - Abstract base class for all data collectors
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Handles common functionality like scheduling and thread management.
    Subclasses should implement the collect() method.
    """
    
    def __init__(self, interval: int = 60):
        """
        Initialize the collector with collection interval.
        
        Args:
            interval: Collection interval in seconds
        """
        self.interval = interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._last_collection_time = 0
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        Collect data from the source.
        
        This method should be implemented by subclasses.
        
        Returns:
            Dict containing the collected data
        """
        pass
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the collected data before storage.
        
        This method can be overridden by subclasses to perform
        additional processing on the collected data.
        
        Args:
            data: The collected data
            
        Returns:
            The processed data
        """
        return data
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        Store the processed data.
        
        This method can be overridden by subclasses to store
        the data in a specific way.
        
        Args:
            data: The processed data to store
        """
        logger.debug(f"Storing data: {data}")
    
    def _collection_loop(self) -> None:
        """
        Main collection loop.
        
        This method runs in a separate thread and performs
        the data collection at the specified interval.
        """
        logger.debug(f"{self.__class__.__name__} collection loop started")
        
        while self.running:
            # Check if it's time to collect data
            current_time = time.time()
            time_since_last = current_time - self._last_collection_time
            
            if time_since_last >= self.interval:
                try:
                    # Collect data
                    data = self.collect()
                    
                    # Process data
                    processed_data = self.process_data(data)
                    
                    # Store data
                    self.store_data(processed_data)
                    
                    # Update last collection time
                    self._last_collection_time = time.time()
                except Exception as e:
                    logger.error(f"Error during data collection: {e}", exc_info=True)
            
            # Sleep for a short time to avoid busy waiting
            # Don't sleep for the full interval to ensure we collect at 
            # the specified interval even if collection takes time
            time.sleep(1)
    
    def start(self) -> None:
        """Start the collector."""
        if self.running:
            logger.warning(f"{self.__class__.__name__} is already running")
            return
        
        logger.info(f"Starting {self.__class__.__name__}")
        self.running = True
        
        # Perform initial collection
        try:
            data = self.collect()
            processed_data = self.process_data(data)
            self.store_data(processed_data)
            self._last_collection_time = time.time()
        except Exception as e:
            logger.error(f"Error during initial data collection: {e}", exc_info=True)
        
        # Start collection thread
        self.thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.thread.start()
        
        logger.info(f"{self.__class__.__name__} started successfully")
    
    def stop(self) -> None:
        """Stop the collector."""
        if not self.running:
            logger.warning(f"{self.__class__.__name__} is not running")
            return
        
        logger.info(f"Stopping {self.__class__.__name__}")
        self.running = False
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=self.interval)
        
        logger.info(f"{self.__class__.__name__} stopped successfully") 