"""
Security Alert Manager - Handles security events and notifications
"""

import logging
import datetime
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional

from src.core.config import Config

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Alert Manager for Network Monitor.
    
    Handles security alerts and notifications, including email alerts
    for security events and anomalies.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the Alert Manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.alert_history = []
        self.last_alert_time = {}  # Track last alert time by type to prevent flooding
        
        # Check if email alerts are configured
        self.email_configured = bool(
            config.alert_email and 
            config.smtp_server and 
            config.smtp_port
        )
        
        if not self.email_configured:
            logger.warning("Email alerts are not configured")
    
    def trigger_alert(self, event_type: str, severity: str, 
                     details: Dict[str, Any], source_device: Optional[Dict[str, Any]] = None,
                     target_device: Optional[Dict[str, Any]] = None) -> bool:
        """
        Trigger a security alert.
        
        Args:
            event_type: Type of security event
            severity: Severity level (high, medium, low)
            details: Event details
            source_device: Source device information (optional)
            target_device: Target device information (optional)
            
        Returns:
            True if alert was triggered, False otherwise
        """
        timestamp = datetime.datetime.now().isoformat()
        
        # Check if we should throttle this alert
        if not self._should_send_alert(event_type, severity):
            logger.debug(f"Throttling {severity} {event_type} alert")
            return False
        
        # Create alert data
        alert_data = {
            "event_type": event_type,
            "severity": severity,
            "timestamp": timestamp,
            "details": details
        }
        
        # Add device information if available
        if source_device:
            alert_data["source_device"] = source_device
        if target_device:
            alert_data["target_device"] = target_device
        
        # Add to alert history
        self.alert_history.append(alert_data)
        
        # Maintain history size
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
        
        # Update last alert time
        self.last_alert_time[event_type] = timestamp
        
        # Log the alert
        logger.warning(f"Security alert: {severity} {event_type} - {details.get('message', '')}")
        
        # Send email notification if configured
        if self.email_configured and severity in ["high", "medium"]:
            self._send_email_alert(alert_data)
        
        return True
    
    def _should_send_alert(self, event_type: str, severity: str) -> bool:
        """
        Check if an alert should be sent based on throttling rules.
        
        Args:
            event_type: Type of security event
            severity: Severity level
            
        Returns:
            True if alert should be sent, False otherwise
        """
        # Always send high severity alerts
        if severity == "high":
            return True
        
        # Get last alert time for this event type
        last_time = self.last_alert_time.get(event_type)
        if not last_time:
            return True
        
        # Parse timestamp
        try:
            last_dt = datetime.datetime.fromisoformat(last_time)
            now = datetime.datetime.now()
            time_diff = (now - last_dt).total_seconds()
            
            # Throttle based on severity
            if severity == "medium" and time_diff < 300:  # 5 minutes
                return False
            elif severity == "low" and time_diff < 1800:  # 30 minutes
                return False
        except ValueError:
            # If time parsing fails, allow the alert
            return True
        
        return True
    
    def _send_email_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send an email alert.
        
        Args:
            alert_data: Alert data
            
        Returns:
            True if email was sent, False otherwise
        """
        if not self.email_configured:
            return False
        
        try:
            # Get email settings from config
            recipient = self.config.alert_email
            smtp_server = self.config.smtp_server
            smtp_port = self.config.smtp_port
            smtp_username = self.config.smtp_username
            smtp_password = self.config.smtp_password
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_username or f"network-monitor@{socket.gethostname()}"
            msg['To'] = recipient
            
            # Set subject based on severity and event type
            severity = alert_data["severity"].upper()
            event_type = alert_data["event_type"]
            msg['Subject'] = f"[{severity}] Network Monitor Alert: {event_type}"
            
            # Build email body
            body = self._format_alert_email(alert_data)
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                if smtp_port == 587:
                    server.starttls()
            
            # Login if credentials provided
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Sent email alert to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
            return False
    
    def _format_alert_email(self, alert_data: Dict[str, Any]) -> str:
        """
        Format an alert email body.
        
        Args:
            alert_data: Alert data
            
        Returns:
            Formatted email body
        """
        # Get alert data
        timestamp = alert_data["timestamp"]
        severity = alert_data["severity"].upper()
        event_type = alert_data["event_type"]
        details = alert_data["details"]
        message = details.get("message", "No details provided")
        
        # Format timestamp
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        
        # Build email body
        body = [
            f"Network Monitor Security Alert",
            f"",
            f"Time: {timestamp}",
            f"Severity: {severity}",
            f"Event Type: {event_type}",
            f"",
            f"Message:",
            f"{message}",
            f""
        ]
        
        # Add event details
        body.append("Details:")
        for key, value in details.items():
            if key != "message":
                body.append(f"- {key}: {value}")
        
        # Add source device information if available
        if "source_device" in alert_data:
            source = alert_data["source_device"]
            body.append("")
            body.append("Source Device:")
            
            if "hostname" in source and source["hostname"]:
                body.append(f"- Hostname: {source['hostname']}")
            
            for key in ["ip", "mac", "vendor", "device_type"]:
                if key in source and source[key]:
                    body.append(f"- {key}: {source[key]}")
        
        # Add target device information if available
        if "target_device" in alert_data:
            target = alert_data["target_device"]
            body.append("")
            body.append("Target Device:")
            
            if "hostname" in target and target["hostname"]:
                body.append(f"- Hostname: {target['hostname']}")
            
            for key in ["ip", "mac", "vendor", "device_type"]:
                if key in target and target[key]:
                    body.append(f"- {key}: {target[key]}")
        
        # Add network monitor information
        body.append("")
        body.append("This alert was generated by Network Monitor running on "
                  f"{socket.gethostname()}.")
        
        return "\n".join(body)
    
    def get_recent_alerts(self, limit: int = 10, 
                         severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent alerts.
        
        Args:
            limit: Maximum number of alerts to return
            severity: Filter by severity
            
        Returns:
            List of recent alerts
        """
        if severity:
            # Filter by severity
            alerts = [a for a in self.alert_history if a["severity"] == severity]
        else:
            alerts = self.alert_history.copy()
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a["timestamp"], reverse=True)
        
        # Apply limit
        return alerts[:limit] 