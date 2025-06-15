"""Module that manages logging configuration for the application.

This module is responsible for setting up loggers used throughout the application.
It provides a custom formatter that formats timestamps in UTC and
a configuration function to initialize the logger.
"""
import logging
from datetime import datetime, timezone

class UTCFormatter(logging.Formatter):
    """Class that formats log timestamps in ISO 8601 format with UTC timezone.

    Inherits from logging.Formatter and overrides the formatTime method to
    display log timestamps always in UTC.
    """
    def formatTime(self, record, datefmt=None):
        """Converts the log record creation time to a UTC ISO format string.

        Args:
            record (logging.LogRecord): Log record object.
            datefmt (str, optional): Date format string.
                This is ignored in this formatter. Defaults to None.

        Returns:
            str: Timestamp string in ISO 8601 format with UTC timezone.
        """
        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

def setup_logger(debug=False):
    """Sets up the application's root logger.

    Configures a StreamHandler for console output and applies a UTCFormatter
    so that timestamps are in UTC. All existing handlers are removed and
    replaced with new handlers.

    Args:
        debug (bool, optional): If True, sets the log level to DEBUG.
            If False, sets it to INFO. Defaults to False.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Get the root logger
    root_logger = logging.getLogger()

    # Remove all existing handlers (to prevent duplicate configurations or unintended output)
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Configure a new console handler and UTC formatter
    handler = logging.StreamHandler()
    formatter = UTCFormatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Adjust log levels for libraries (as needed)
    # logging.getLogger("urllib3").setLevel(logging.WARNING) 