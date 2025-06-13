# src/config.py
"""Configuration values used throughout the application.

This module defines configuration values shared across the application,
including serial communication, B-route authentication information,
data output destinations, and ECHONET Lite related constants.

Settings are loaded from environment variables, with predefined
default values used when environment variables are not present.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Application version
try:
    # When package is installed
    from importlib.metadata import version
    try:
        VERSION = version("hems-data-collector")
    except:
        # In development environment, try to get directly from scm
        try:
            from setuptools_scm import get_version
            VERSION = get_version(root='..', relative_to=__file__)
        except Exception as e:
            logger.debug(f"Could not get version from setuptools_scm: {e}")
            VERSION = "development"  # Final fallback
except ImportError:
    VERSION = "development"  # Fallback

# Serial communication settings
SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')  # USB dongle serial port (adjust for your environment)
SERIAL_RATE = int(os.environ.get('SERIAL_RATE', 115200))          # Baud rate

# B-route authentication information (provided by power company)
B_ROUTE_ID = os.environ.get('B_ROUTE_ID', "00000000000000000000000000000000")  # Authentication ID
B_ROUTE_PASSWORD = os.environ.get('B_ROUTE_PASSWORD', "00000000000000000000000000000000")  # Password

# Data file
DEFAULT_DATA_FILE = "hems_data.dat"

# Google Cloud Pub/Sub settings
GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID', "your-project-id")  # Google Cloud project
GCP_TOPIC_NAME = os.getenv('GCP_TOPIC_NAME', 'hems-data')

# Default execution schedule (every 5 minutes)
DEFAULT_SCHEDULE = '*/5 * * * *' 
# Default execution interval (seconds)
DEFAULT_INTERVAL = 300
# Default Webhook URL
DEFAULT_WEBHOOK_URL = os.environ.get('WEBHOOK_URL', "http://localhost:8000/webhook")
# Default timezone
LOCAL_TIMEZONE = os.environ.get('LOCAL_TIMEZONE', "Asia/Tokyo")

# ECHONET Lite related constants
ECHONET_PROPERTY_CODES = {
    'CUMULATIVE_POWER': "E0",  # Cumulative power consumption
    'CUMULATIVE_POWER_UNIT': "E1", # Cumulative power unit
    'HISTORICAL_CUMULATIVE_POWER': "EA", # Regular cumulative power measurement
    'CUMULATIVE_POWER_HISTORY_1': "E2", # Cumulative power measurement history 1
    'SET_CUMULATIVE_HISTORY_DAY': "E5",  # Cumulative history collection day 1
    'INSTANT_POWER': "E7",     # Instantaneous power measurement
    'CURRENT_VALUE': "E8",     # Instantaneous current measurement
}

# CSV output headers
CSV_HEADERS = [
    'timestamp', 
    'cumulative_power_kwh', 
    'instant_power_w', 
    'current_a',
    'current_r_a', 
    'current_t_a',
    'historical_timestamp',
    'historical_cumulative_power_kwh',
    'recent_30min_timestamp',
    'recent_30min_consumption_kwh'
]