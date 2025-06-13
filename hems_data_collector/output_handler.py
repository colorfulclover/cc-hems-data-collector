# src/output_handler.py
"""Module responsible for outputting collected power data.

Provides handlers for outputting power consumption data in various formats
(standard output, file, Google Cloud Pub/Sub, Webhook).
"""
import os
import logging
import json
import yaml
import requests
from datetime import datetime

from hems_data_collector.config import CSV_HEADERS

logger = logging.getLogger(__name__)

class OutputHandler:
    """Class for handling data output processing.

    Attributes:
        output_type (str): Output type ('stdout', 'file', 'gcloud', 'webhook').
        output_format (str): Output format ('json', 'yaml', 'csv').
        filepath (str): Path for file output.
        project_id (str): Google Cloud project ID.
        topic_name (str): Pub/Sub topic name.
        publisher (pubsub_v1.PublisherClient): Pub/Sub client.
        topic_path (str): Full path of the Pub/Sub topic.
        webhook_url (str): Destination URL for webhook.
    """
    
    def __init__(self, output_type, output_format='json', filepath=None, 
                 project_id=None, topic_name=None, webhook_url=None):
        """Initialize the OutputHandler.

        Args:
            output_type (str): Output type ('stdout', 'file', 'gcloud', 'webhook').
            output_format (str, optional): Output format ('json', 'yaml', 'csv').
                For 'gcloud' or 'webhook' types, this is fixed to 'json'.
                Defaults to 'json'.
            filepath (str, optional): Path for file output.
                Required for 'file' type. Defaults to None.
            project_id (str, optional): Google Cloud project ID.
                Required for 'gcloud' type. Defaults to None.
            topic_name (str, optional): Pub/Sub topic name.
                Required for 'gcloud' type. Defaults to None.
            webhook_url (str, optional): Destination URL for webhook.
                Required for 'webhook' type. Defaults to None.
        """
        self.type = output_type
        self.format = output_format
        self.filepath = filepath
        self.project_id = project_id
        self.topic_name = topic_name
        self.webhook_url = webhook_url
        self.publisher = None
        self.topic_path = None
        self.headers = {'Content-Type': 'application/json'}
        
        # Initialize Google Cloud Pub/Sub client
        if self.type == 'gcloud':
            try:
                from google.cloud import pubsub_v1
                self.publisher = pubsub_v1.PublisherClient()
                self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
            except ImportError:
                self.publisher = None
                self.topic_path = None
                logger.error("google-cloud-pubsub is not installed.")
            except Exception as e:
                self.publisher = None
                self.topic_path = None
                logger.error(f"Failed to initialize Pub/Sub client: {e}")

    def output(self, data):
        """Output data in the specified format and destination.

        Args:
            data (dict): Power data to be output.
        """
        try:
            data_str = self._get_formatted_string(data)
            if not data_str:
                return

            if self.type == 'stdout':
                print(data_str)
            elif self.type == 'file':
                self._output_to_file(data_str)
            elif self.type == 'gcloud':
                self._output_to_gcloud(data_str)
            elif self.type == 'webhook':
                self._output_to_webhook(data_str)
        except Exception as e:
            logger.error(f"Error occurred during output to {self.type}: {e}")

    def _get_formatted_string(self, data):
        """Convert data to a string in the specified format."""
        if self.format == 'json':
            return json.dumps(data)
        elif self.format == 'yaml':
            return yaml.dump(data, default_flow_style=False)
        elif self.format == 'csv':
            # Write headers if file doesn't exist or is empty
            if self.filepath and (not os.path.exists(self.filepath) or os.path.getsize(self.filepath) == 0):
                self._output_to_file(','.join(CSV_HEADERS), append=False)
            
            row_data = [
                str(data.get('timestamp', '')),
                str(data.get('cumulative_power_kwh', '')),
                str(data.get('instant_power_w', '')),
                str(data.get('current_a', '')),
                str(data.get('current_r_a', '')),
                str(data.get('current_t_a', '')),
                str(data.get('historical_timestamp', '')),
                str(data.get('historical_cumulative_power_kwh', '')),
                str(data.get('recent_30min_timestamp', '')),
                str(data.get('recent_30min_consumption_kwh', ''))
            ]
            return ','.join(row_data)
        return None

    def _output_to_file(self, data_str, append=True):
        """Write string to a file."""
        mode = 'a' if append else 'w'
        try:
            with open(self.filepath, mode, encoding='utf-8') as f:
                f.write(data_str + '\n')
            logger.info(f"Data written to file: {self.filepath}")
        except IOError as e:
            logger.error(f"File write error ({self.filepath}): {e}")

    def _output_to_gcloud(self, data_str):
        """Send data to Google Cloud Pub/Sub."""
        if not self.publisher or not self.topic_path:
            logger.error("Pub/Sub client is not initialized.")
            return

        future = self.publisher.publish(self.topic_path, data_str.encode('utf-8'))
        future.result()  # Wait for sending to complete
        logger.info(f"Message sent to Google Cloud Pub/Sub topic: {self.topic_path}")
    
    def _output_to_webhook(self, data_str):
        """POST data as JSON to a webhook.

        Args:
            data_str (str): JSON string to send.
        """
        if not self.webhook_url:
            logger.error("Webhook URL is not set.")
            return

        try:
            response = requests.post(self.webhook_url, data=data_str, headers=self.headers, timeout=10)
            response.raise_for_status()  # Raises exception for non-2xx status codes
            logger.info(f"Data sent to webhook: {self.webhook_url} (status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send to webhook: {e}")