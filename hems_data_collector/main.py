# src/main.py
"""Main module of the HEMS data collection application.

Interpreting command-line arguments, configuring logging,
initializing SmartMeterClient and starting the data collection process.
"""
import time
import logging
import argparse
import traceback
from datetime import datetime, timezone
from croniter import croniter

from hems_data_collector.config import (
    VERSION,
    DEFAULT_DATA_FILE, GCP_PROJECT_ID, GCP_TOPIC_NAME,
    SERIAL_PORT, SERIAL_RATE, DEFAULT_SCHEDULE, DEFAULT_INTERVAL,
    DEFAULT_WEBHOOK_URL
)
from hems_data_collector.serial_client import SmartMeterClient
from hems_data_collector.output_handler import OutputHandler
from hems_data_collector.logger_config import setup_logger

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Object containing parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description='A tool for collecting data from smart meters (HEMS)')
    
    # Output types
    parser.add_argument(
        '--output', '-o', choices=['stdout', 'file', 'gcloud', 'webhook'], 
        nargs='*', default=None, 
        help='Select one or more output types (e.g., --output stdout file). (Default: None, log output only)'
    )
    
    # Output format
    parser.add_argument('--format', '-f', choices=['json', 'yaml', 'csv'], 
                        default='json', help='Output format (Default: json)')
    
    # File output path
    parser.add_argument('--file', default=DEFAULT_DATA_FILE, 
                        help=f'File output path (Default: {DEFAULT_DATA_FILE})')
    
    # Google Cloud Pub/Sub settings
    parser.add_argument('--gcp-project', default=GCP_PROJECT_ID, 
                        help=f'Google Cloud project ID (Default: {GCP_PROJECT_ID})')
    parser.add_argument('--gcp-topic', default=GCP_TOPIC_NAME, 
                        help=f'Pub/Sub topic name (Default: {GCP_TOPIC_NAME})')
    
    # Webhook settings
    parser.add_argument('--webhook-url', default=DEFAULT_WEBHOOK_URL,
                        help=f'Webhook destination URL (Default: {DEFAULT_WEBHOOK_URL})')
    
    # Serial port settings
    parser.add_argument('--port', default=SERIAL_PORT, 
                        help=f'Serial port (Default: {SERIAL_PORT})')
    parser.add_argument('--baudrate', type=int, default=SERIAL_RATE, 
                        help=f'Baud rate (Default: {SERIAL_RATE})')

    # Smart meter information
    parser.add_argument('--meter-channel', type=str, help='Smart meter channel')
    parser.add_argument('--meter-panid', type=str, help='Smart meter PAN ID')
    parser.add_argument('--meter-ipv6', type=str, help='Smart meter IPv6 address')
    
    # Execution mode settings
    parser.add_argument(
        '--mode', type=str, default='schedule', choices=['schedule', 'interval'],
        help='Execution mode (Default: schedule)'
    )
    # Schedule settings
    parser.add_argument(
        '--schedule', '-s', type=str, default=DEFAULT_SCHEDULE,
        help=f'Data collection schedule (crontab format, valid in schedule mode, Default: "{DEFAULT_SCHEDULE}")'
    )
    # Interval settings
    parser.add_argument(
        '--interval', '-i', type=int, default=DEFAULT_INTERVAL,
        help=f'Data collection interval (seconds, valid in interval mode, Default: {DEFAULT_INTERVAL})'
    )
    
    # Log level settings
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode (outputs detailed logs)')
    
    # Version information
    parser.add_argument('--version', '-v', action='version', version=f'%(prog)s {VERSION}',
                        help='Display version information and exit')

    return parser.parse_args()


def setup_output_handlers(args):
    """Set up a list of output handlers based on command-line arguments.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        list[OutputHandler]: List of configured OutputHandler instances.
    """
    output_handlers = []
    
    if not args.output:
        return output_handlers

    if 'stdout' in args.output:
        output_handlers.append(OutputHandler('stdout', args.format))
    
    if 'file' in args.output:
        file_ext = {'json': '.json', 'yaml': '.yaml', 'csv': '.csv'}
        file_path = args.file
        if not any(file_path.endswith(ext) for ext in file_ext.values()):
            file_path += file_ext.get(args.format, '')
        
        output_handlers.append(OutputHandler('file', args.format, filepath=file_path))
    
    if 'gcloud' in args.output:
        try:
            from google.cloud import pubsub_v1
            output_handlers.append(OutputHandler('gcloud', 'json', project_id=args.gcp_project, topic_name=args.gcp_topic))
        except ImportError:
            logger.error("Google Cloud Pub/Sub feature is not available. Please install the package: pip install google-cloud-pubsub")

    if 'webhook' in args.output:
        output_handlers.append(OutputHandler('webhook', 'json', webhook_url=args.webhook_url))
    
    return output_handlers


def main():
    """Main execution function of the application.

    Parses arguments, configures logging, initializes output handlers and client,
    and starts the main data collection loop.
    """
    args = parse_args()
    
    # Configure logging
    setup_logger(args.debug)
    logger.info("Starting hems_data_collector")

    if args.debug:
        logger.info("Debug mode enabled")
    
    # Create output handlers
    output_handlers = setup_output_handlers(args)
    
    client = SmartMeterClient(
        port=args.port,
        baudrate=args.baudrate,
        output_handlers=output_handlers,
        meter_channel=args.meter_channel,
        meter_pan_id=args.meter_panid,
        meter_ipv6_addr=args.meter_ipv6
    )
    
    try:
        # Start output thread
        client.start_output_thread()
        
        # Initialize and connect to smart meter
        if not client.initialize():
            logger.error("Initialization failed. Exiting program.")
            return
        
        # Periodically retrieve data
        if args.mode == 'schedule':
            # Schedule mode
            base_time = datetime.now(timezone.utc)
            try:
                cron = croniter(args.schedule, base_time)
                logger.info(f"Running in schedule mode. Schedule: '{args.schedule}'")
            except ValueError as e:
                logger.error(f"Invalid cron format schedule: {args.schedule} - {e}")
                return

            while client.running:
                # Wait until next execution time
                next_run_datetime = cron.get_next(datetime)
                wait_seconds = (next_run_datetime - datetime.now(timezone.utc)).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"Next execution at {next_run_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')} ({wait_seconds:.1f} seconds later)")
                    sleep_end = time.time() + wait_seconds
                    while time.time() < sleep_end:
                        if not client.running:
                            # If stopped during sleep, exit the loop
                            break
                        time.sleep(min(1, sleep_end - time.time()))
                
                if not client.running:
                    logger.info("Client has stopped.")
                    break

                # Retrieve data
                try:
                    meter_data = client.get_meter_data()
                    if meter_data:
                        client.data_queue.put(meter_data)
                        logger.info(f"Data retrieved: {meter_data}")
                    else:
                        logger.info("No data could be retrieved.")
                except Exception as e:
                    logger.error(f"Error occurred during data retrieval: {e}")

        elif args.mode == 'interval':
            # Interval mode
            logger.info(f"Running in interval mode. Interval: {args.interval} seconds")
            while client.running:
                if not client.running:
                    logger.info("Client has stopped.")
                    break

                # Retrieve data
                try:
                    meter_data = client.get_meter_data()
                    if meter_data:
                        # Add to data queue
                        client.data_queue.put(meter_data)
                        logger.info(f"Data retrieved: {meter_data}")
                    else:
                        logger.info("No data could be retrieved.")

                except KeyboardInterrupt:
                        raise
                except Exception as e:
                    logger.error(f"Error occurred during data retrieval: {e}")

                # Wait for specified interval
                logger.info(f"Will retrieve data again in {args.interval} seconds...")
                sleep_end = time.time() + args.interval
                while time.time() < sleep_end:
                    if not client.running:
                        # If stopped during sleep, exit the loop
                        break
                    time.sleep(min(1, sleep_end - time.time()))

    except KeyboardInterrupt:
        logger.info("Exiting program...")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        client.stop_output_thread()
        client.close_connection()
        logger.info("Cleanup completed and program terminated.")


if __name__ == "__main__":
    main()