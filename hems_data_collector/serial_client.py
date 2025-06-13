# src/serial_client.py
"""Client for handling serial communication with smart meters.

Communicates with smart meters via Wi-SUN module,
establishes PANA sessions, sends and receives ECHONET Lite commands,
and retrieves power data.
"""
import serial
import time
import re
import logging
import traceback
from queue import Queue, Empty
import threading

from hems_data_collector.config import (
    SERIAL_PORT, SERIAL_RATE, B_ROUTE_ID, B_ROUTE_PASSWORD, 
    ECHONET_PROPERTY_CODES
)
from hems_data_collector.utils import (
    parse_echonet_response, parse_cumulative_power, parse_power_unit,
    parse_instant_power, parse_current_value, get_current_timestamp,
    parse_echonet_frame, parse_historical_power, parse_cumulative_power_history
)

logger = logging.getLogger(__name__)

class SmartMeterClient:
    """Main class for managing communication with smart meters.

    Handles opening/closing serial ports, initializing Wi-SUN modules, managing PANA sessions,
    requesting ECHONET Lite properties, and controlling data output threads.

    Attributes:
        port (str): Serial port name (e.g., '/dev/ttyUSB0').
        baudrate (int): Baud rate (e.g., 115200).
        ser (serial.Serial): `pyserial` serial port instance.
        connected (bool): Flag indicating whether a PANA session is established.
        ipv6_addr (str): IPv6 address of the connected smart meter.
        output_handlers (list): List of data output handlers.
        data_queue (Queue): Queue holding output data.
        output_thread (threading.Thread): Worker thread handling output processing.
        running (bool): Flag controlling thread execution state.
    """
    def __init__(self, port=SERIAL_PORT, baudrate=SERIAL_RATE, output_handlers=None,
                 meter_channel=None, meter_pan_id=None, meter_ipv6_addr=None):
        """Initialize the SmartMeterClient.

        Args:
            port (str, optional): Serial port to use.
                Defaults to SERIAL_PORT.
            baudrate (int, optional): Communication baud rate.
                Defaults to SERIAL_RATE.
            output_handlers (list, optional): List of data output handlers.
                Defaults to None.
            meter_channel (str, optional): Smart meter channel. If not specified, will scan.
            meter_pan_id (str, optional): Smart meter PAN ID. If not specified, will scan.
            meter_ipv6_addr (str, optional): Smart meter IPv6 address. If not specified, will scan.
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.ipv6_addr = meter_ipv6_addr
        self.meter_channel = meter_channel
        self.meter_pan_id = meter_pan_id
        self.output_handlers = output_handlers or []
        self.data_queue = Queue()
        self.output_thread = None
        self.running = False
    
    def open_connection(self):
        """Open the serial port.

        Returns:
            bool: True if port opening succeeds, False if it fails.
        """
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=10  # Read timeout (seconds)
            )
            logger.info(f"Opened serial port {self.port} (baud rate: {self.baudrate})")
            return True
        except Exception as e:
            logger.error(f"Error opening serial port: {e}")
            return False
    
    def close_connection(self):
        """Close the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Closed serial port")
    
    def send_command(self, command, command_parts=None, wait_time=1, expected_response=None, timeout=10, add_newline=True):
        """Send a command and wait for a response.

        This function can send a text command followed by additional binary data.

        Args:
            command (str): The text command part to send.
            command_parts (bytes, optional): Additional binary data to send
                after the command. Defaults to None.
            wait_time (int, optional): Number of seconds to wait after sending the command.
                Defaults to 1.
            expected_response (str, optional): String expected to be included in the response.
                If found, returns the response immediately. Defaults to None.
            timeout (int, optional): Maximum number of seconds to wait for a response. Defaults to 10.
            add_newline (bool, optional): Whether to append a newline code
                `\\r\\n` at the end of the text command. Defaults to True.

        Returns:
            str | None: The received response string. None if timed out.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Serial port is not open")
            return None
        
        # Add a newline to the end of the command (if needed)
        if add_newline and not command.endswith('\r\n'):
            command += '\r\n'

        # Send command
        if  command_parts is None:
            logger.debug(f"Sent: {command.strip()}")
            self.ser.write(command.encode('utf-8'))
        else:
            logger.debug(f"Sent: {command.strip()} {command_parts}")
            self.ser.write(command.encode('utf-8') + command_parts)
        self.ser.flush()

        # Wait for response
        time.sleep(wait_time)

        # Read response
        response = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                logger.debug(f"Received: {line}")
                response += line + "\n"
                
                # Check if the expected response is included
                if expected_response and expected_response in line:
                    return response

                # If ERROR is included
                if "ERROR" in line:
                    logger.error(f"Received error response: {line}")
                    return response

            else:
                time.sleep(0.1)  # Wait a little
        
        return response
    
    def initialize(self):
        """Initialize the Wi-SUN module and connect to the smart meter.

        Executes a sequence of steps including B-route authentication, PAN scanning,
        and PANA session establishment.

        Returns:
            bool: True if initialization and connection succeed, False if they fail.
        """
        if not self.open_connection():
            return False
        
        # Set scan mode to active
        logger.info("Starting initialization...")

        # Get version information
        version_response = self.send_command("SKVER")
        bp35a1_version = "Unknown"
        if version_response:
            for line in version_response.splitlines():
                if line.startswith("EVER"):
                    bp35a1_version = line
                    break
        logger.info(f"FW version: {bp35a1_version.strip()}")
        
        # Set B-route authentication information
        logger.info("Setting B-route authentication information...")
        self.send_command(f"SKSETRBID {B_ROUTE_ID}")
        self.send_command(f"SKSETPWD C {B_ROUTE_PASSWORD}")
        
        # Check if channel, PAN ID, and IPv6 address are specified
        if self.meter_channel and self.meter_pan_id and self.ipv6_addr:
            logger.info("Attempting to connect using the specified information...")
            logger.info(f"Setting channel to {self.meter_channel}...")
            self.send_command(f"SKSREG S2 {self.meter_channel}")
            
            logger.info(f"Setting PAN ID to {self.meter_pan_id}...")
            self.send_command(f"SKSREG S3 {self.meter_pan_id}")
            
            # In this case, self.ipv6_addr is already set during initialization
            logger.info(f"IPv6 address: {self.ipv6_addr}")

        else:
            logger.info("Obtaining connection information via scanning...")
            # Execute network scan
            logger.info(f"Executing network scan...")
            response = self.send_command(f"SKSCAN 2 FFFFFFFF 6", wait_time=20)
            
            # Get PAN address from scan results
            pan_addr_match = re.search(r'Addr:([0-9A-F]{16})', response)
            if not pan_addr_match:
                logger.error("PAN descriptor not found")
                return False
                
            pan_addr = pan_addr_match.group(1)
            logger.info(f"Found PAN address: {pan_addr}")

            # Convert PAN address to IPv6 address
            logger.info(f"Converting PAN address: {pan_addr} to IPv6 address...")
            ipv6_addr_response = self.send_command(f"SKLL64 {pan_addr}")
            ipv6_addr_match = re.search(r'([0-9A-Fa-f]{1,4}(:[0-9A-Fa-f]{1,4}){7})', ipv6_addr_response)
            if not ipv6_addr_match:
                logger.error("IPv6 address not found")
                return False
            self.ipv6_addr = ipv6_addr_match.group(1)
            logger.info(f"IPv6 address: {self.ipv6_addr}")
            
            # Set channel
            channel_match = re.search(r'Channel:([0-9A-F]{2})', response)
            if channel_match:
                channel = channel_match.group(1)
                logger.info(f"Setting channel to {channel}...")
                self.send_command(f"SKSREG S2 {channel}")
            
            # Set PAN ID
            pan_id_match = re.search(r'Pan ID:([0-9A-F]{4})', response)
            if pan_id_match:
                pan_id = pan_id_match.group(1)
                logger.info(f"Setting PANID to {pan_id}...")
                self.send_command(f"SKSREG S3 {pan_id}")
        
        # Connect to PANA
        logger.info("Connecting to PANA...")
        # Expect an "OK" response to the SKJOIN command. wait_time is short as we wait for OK in send_command's internal timeout.
        join_response = self.send_command(f"SKJOIN {self.ipv6_addr}", expected_response="OK", wait_time=0.1)

        if not join_response or "OK" not in join_response:
            logger.error(f"Failed to send PANA connection command (SKJOIN {self.ipv6_addr}), or no OK response received. Response: {join_response}")
            return False

        # Wait for connection completion (EVENT 25)
        logger.info("Waiting for PANA connection completion (EVENT 25)...")
        event_25_received = False
        for i in range(30):  # Wait up to 30 seconds (PANA connection can take time)
            if not self.running: # If stopped during the process
                 logger.info("Initialization process was interrupted. (While waiting for event)")
                 return False
            
            # Try to read one line from the serial port (in a nearly non-blocking way)
            line = ""
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        logger.debug(f"Received (while waiting for event Loop {i+1}/30): {line}")
                except Exception as e:
                    logger.warning(f"Serial read error while waiting for event: {e}")
                    # The port might have been closed or other issues, so wait a bit and retry
                    time.sleep(0.1)
                    continue
            
            if line.startswith("EVENT 24"): # PANA connection failure
                logger.error("PANA connection failed (EVENT 24)")
                return False
            elif line.startswith("EVENT 25"):  # Connection success event
                logger.info("Connected to smart meter (EVENT 25)")
                self.connected = True
                event_25_received = True
                return True # initialization success
            
            time.sleep(1) # Wait for 1 second

        if not event_25_received:
            logger.error("PANA connection timeout (EVENT 25 not received within 30 seconds)")
            # Consider sending SKTERM to end the PANA session
            # logger.info("Sending SKTERM to end PANA session.")
            # self.send_command("SKTERM", wait_time=1, expected_response="OK")
            return False
        
        logger.error("Failed to connect to smart meter (unexpected flow)")
        return False
    
    def _wait_for_echonet_response(self, property_code, request_tid_hex, expected_esv='72'):
        """Wait for an ECHONET Lite response with the specified TID."""
        logger.info(f"Starting ERXUDP wait (property: {property_code}, ESV: {expected_esv})")
        start_time = time.time()
        while time.time() - start_time < 20: # Set timeout to 20 seconds
            if not self.running:
                logger.info("Data collection was interrupted. (While waiting for ERXUDP)")
                return None
            
            line = ""
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: logger.debug(f"Received (while waiting for ERXUDP): {line}")
                except Exception as e:
                    logger.warning(f"Serial read error while waiting for ERXUDP: {e}")
            
            if not line:
                time.sleep(0.5)
                continue

            if line.startswith("ERXUDP"):
                parts = line.strip().split(' ')
                if len(parts) >= 9:
                    echonet_data_hex = parts[8]
                    parsed_frame = parse_echonet_frame(echonet_data_hex)
                    if not (parsed_frame and parsed_frame['TID'] == request_tid_hex):
                        continue

                    # Check if it's the expected ESV (Get_Res or Set_Res)
                    if parsed_frame['ESV'].upper() == expected_esv.upper():
                        # Check if the property code is included
                        if any(prop['EPC'] == property_code.upper() for prop in parsed_frame['properties']):
                             logger.info(f"ERXUDP received successfully (property: {property_code}): {echonet_data_hex}")
                             return echonet_data_hex
                    # If ESV is an error response like SNA (50 series)
                    elif parsed_frame['ESV'].startswith('5'):
                        logger.warning(f"Received ECHONET Lite error response (SNA): ESV={parsed_frame['ESV']}")
                        return None # Return None for error responses
                    else:
                        logger.debug(f"Not the expected response (ESV={expected_esv}): ESV={parsed_frame['ESV']}")
                        # Ignore other responses and continue waiting
            elif "FAIL" in line:
                logger.error(f"Received FAIL while waiting for ERXUDP: {line}")
                return None
        
        logger.warning(f"ERXUDP wait timeout (property: {property_code})")
        return None

    def get_property(self, property_code, transaction_id=1):
        """Get the value of the specified ECHONET Lite property.

        Sends an ECHONET Lite Get request using the SKSENDTO command and waits for a response via ERXUDP.

        Args:
            property_code (str): EPC code of the property to retrieve (hexadecimal string).
            transaction_id (int, optional): ECHONET Lite transaction ID.
                Defaults to 1.

        Returns:
            str | None: Data portion of the received ECHONET Lite frame (hexadecimal string).
                Returns the frame for successful responses (ESV=72). None if failed.
        """
        if not self.connected:
            logger.error("PANA session is not established. Skipping get_property.")
            return None

        request_tid_hex = format(transaction_id, "04X")
        try:
            # Construct ECHONET Lite frame as bytes
            echonet_lite_frame_bytes = (
                b'\x10\x81'        # EHD
                + transaction_id.to_bytes(2, 'big')        # TID
                + b'\x05\xFF\x01'  # SEOJ (Source)
                + b'\x02\x88\x01'  # DEOJ (Destination)
                + b'\x62'          # ESV (Get)
                + b'\x01'          # OPC (Number of processing properties)
                + int(property_code, 16).to_bytes(1, 'big') # EPC (Property code)
                + b'\x00'          # PDC (Data counter)
            )
        except Exception as e:
            logger.error(f"Failed to construct ECHONET Lite GET frame: {e}")
            return None

        # Calculate DATALEN
        data_len_bytes = len(echonet_lite_frame_bytes)
        datalen_hex_str = format(data_len_bytes, '04X')

        # Assemble SKSENDTO command
        base_sksendto_command = f"SKSENDTO 1 {self.ipv6_addr} 0E1A 1"
        full_sksendto_command = f"{base_sksendto_command} {datalen_hex_str} "

        # 2. Execute SKSENDTO command and check response
        logger.debug(f"Sending SKSENDTO: {full_sksendto_command}")
        sksendto_response = self.send_command(full_sksendto_command, command_parts=echonet_lite_frame_bytes, expected_response="OK", wait_time=0.2, add_newline=False) # wait_time is the time until receiving OK/FAIL response

        if not sksendto_response:
            logger.error(f"No response to SKSENDTO command: {sksendto_response.strip()}")
            return None
        
        if "FAIL" in sksendto_response:
            logger.error(f"SKSENDTO command failed: {sksendto_response.strip()}")
            return None
        
        if "OK" not in sksendto_response:
            logger.error(f"Failed to send SKSENDTO(GET) command, or no OK response received: {sksendto_response.strip()}")
            return None

        return self._wait_for_echonet_response(property_code, request_tid_hex, expected_esv='72')

    def set_property(self, property_code, edt, transaction_id=1):
        """Set the value of the specified ECHONET Lite property (SetC).

        Sends an ECHONET Lite SetC request using the SKSENDTO command and waits for a response via ERXUDP.

        Args:
            property_code (str): EPC code of the property to set (hexadecimal string).
            edt (str): Hexadecimal string of the data (EDT) to set.
            transaction_id (int, optional): ECHONET Lite transaction ID.
                Defaults to 1.

        Returns:
            str | None: Data portion of the received ECHONET Lite frame (hexadecimal string).
                Returns the frame for successful responses (ESV=71). None if failed.
        """
        if not self.connected:
            logger.error("PANA session is not established. Skipping set_property.")
            return None

        request_tid_hex = format(transaction_id, "04X")
        try:
            # Construct ECHONET Lite frame as bytes
            edt_bytes = bytes.fromhex(edt)
            echonet_lite_frame_bytes = (
                b'\x10\x81'        # EHD
                + transaction_id.to_bytes(2, 'big')        # TID
                + b'\x05\xFF\x01'  # SEOJ (Source)
                + b'\x02\x88\x01'  # DEOJ (Destination)
                + b'\x61'          # ESV (SetC)
                + b'\x01'          # OPC (Number of processing properties)
                + int(property_code, 16).to_bytes(1, 'big') # EPC (Property code)
                + len(edt_bytes).to_bytes(1, 'big')      # PDC (Data counter)
                + edt_bytes        # EDT (Data body)
            )
        except Exception as e:
            logger.error(f"Failed to construct ECHONET Lite SET frame: {e}")
            return None

        datalen_hex_str = format(len(echonet_lite_frame_bytes), '04X')
        full_sksendto_command = f"SKSENDTO 1 {self.ipv6_addr} 0E1A 1 {datalen_hex_str} "

        sksendto_response = self.send_command(
            full_sksendto_command, command_parts=echonet_lite_frame_bytes,
            expected_response="OK", wait_time=0.2, add_newline=False
        )

        if not sksendto_response or "OK" not in sksendto_response:
            response_str = sksendto_response.strip() if sksendto_response else "None"
            logger.error(f"Failed to send SKSENDTO(SET) command, or no OK response received: {response_str}")
            return None

        return self._wait_for_echonet_response(property_code, request_tid_hex, expected_esv='71')

    def get_meter_data(self):
        """Retrieve key power data from the smart meter in a single operation."""
        if not self.connected:
            logger.error("Not connected to smart meter")
            return None
        
        data = {}
        data['timestamp'] = get_current_timestamp()
        
        try:
            # First get the cumulative power unit (E1)
            logger.info("Requesting cumulative power unit...")
            unit_response = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_UNIT'], 1)
            unit_hex_value = parse_echonet_response(unit_response, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_UNIT'])
            power_multiplier = parse_power_unit(unit_hex_value)

            # Get cumulative power measurement
            logger.info("Requesting cumulative power...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'], 2)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'])
            if hex_value:
                power_value = parse_cumulative_power(hex_value, power_multiplier)
                if power_value is not None:
                    data['cumulative_power_kwh'] = power_value
                    logger.info(f"Cumulative power: {power_value} kWh (unit multiplier: {power_multiplier})")
            
            # Get instantaneous power measurement
            logger.info("Requesting instantaneous power...")
            response = self.get_property(ECHONET_PROPERTY_CODES['INSTANT_POWER'], 3)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['INSTANT_POWER'])
            if hex_value:
                power_value = parse_instant_power(hex_value)
                if power_value is not None:
                    data['instant_power_w'] = power_value
                    logger.info(f"Instantaneous power: {power_value} W")
            
            # Get instantaneous current measurement
            logger.info("Requesting instantaneous current...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CURRENT_VALUE'], 4)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CURRENT_VALUE'])
            if hex_value:
                current_data = parse_current_value(hex_value)
                if current_data:
                    data.update(current_data)
                    # Adjust key names for log output
                    if current_data.get('current_t_a') is None:
                        # Single-phase
                        logger.info(f"Instantaneous current: {current_data.get('current_a')} A")
                    else:
                        # Three-phase
                        logger.info(f"Instantaneous current: R-phase={current_data.get('current_r_a')} A, T-phase={current_data.get('current_t_a')} A (total: {current_data.get('current_a')} A)")
            
            # Get regular cumulative power measurement (EA)
            logger.info("Requesting regular cumulative power...")
            response = self.get_property(ECHONET_PROPERTY_CODES['HISTORICAL_CUMULATIVE_POWER'], 5)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['HISTORICAL_CUMULATIVE_POWER'])
            if hex_value:
                historical_data = parse_historical_power(hex_value, power_multiplier)
                if historical_data:
                    data.update(historical_data)
                    logger.info(f"Regular cumulative power: {historical_data['historical_cumulative_power_kwh']} kWh ({historical_data['historical_timestamp']})")

            # Get 30-minute power consumption from cumulative power measurement history 1 (E2)
            today_history_hex = None
            logger.info("Setting cumulative history collection day (E5) to 'today'...")
            if self.set_property(ECHONET_PROPERTY_CODES['SET_CUMULATIVE_HISTORY_DAY'], '00', 6):
                logger.info("Requesting 'today's' cumulative power history 1 (E2)...")
                today_history_frame = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'], 7)
                today_history_hex = parse_echonet_response(today_history_frame, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'])
            else:
                logger.warning("Failed to set cumulative history collection day (E5) to 'today'.")

            # First try to calculate using only today's data
            consumption_data = parse_cumulative_power_history(today_history_hex, multiplier=power_multiplier)

            # If calculation fails (e.g., date change), get yesterday's data and retry
            if not consumption_data and today_history_hex is not None:
                logger.info("Data may be insufficient for calculating 30-minute power consumption, retrieving yesterday's history.")
                yesterday_history_hex = None
                logger.info("Setting cumulative history collection day (E5) to 'yesterday'...")
                if self.set_property(ECHONET_PROPERTY_CODES['SET_CUMULATIVE_HISTORY_DAY'], '01', 8):
                    logger.info("Requesting 'yesterday's' cumulative power history 1 (E2)...")
                    yesterday_history_frame = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'], 9)
                    yesterday_history_hex = parse_echonet_response(yesterday_history_frame, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'])
                else:
                    logger.warning("Failed to set cumulative history collection day (E5) to 'yesterday'.")

                # Recalculate using both today's and yesterday's data
                consumption_data = parse_cumulative_power_history(
                    today_history_hex,
                    yesterday_edt=yesterday_history_hex,
                    multiplier=power_multiplier
                )

            if consumption_data:
                data.update(consumption_data)
                logger.info(f"Recent 30-minute power consumption: {consumption_data['recent_30min_consumption_kwh']} kWh ({consumption_data['recent_30min_timestamp']})")
            else:
                logger.info("Ultimately, the 30-minute power consumption could not be calculated.")

            return data if len(data) > 1 else None  # Return only if there is data other than timestamp
            
        except Exception as e:
            logger.error(f"Error occurred during data retrieval: {e}")
            traceback.print_exc()
            return None

    def start_output_thread(self):
        """Start the worker thread for data output."""
        self.running = True
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.daemon = True
        self.output_thread.start()
    
    def _output_worker(self):
        """Worker thread that retrieves data from the data queue and passes it to output handlers."""
        while self.running:
            try:
                # Get data from queue (blocking)
                data = self.data_queue.get(timeout=1.0)

                # Send data to each output handler
                for handler in self.output_handlers:
                    try:
                        handler.output(data)
                    except Exception as e:
                        logger.error(f"Data output error: {e}")

                self.data_queue.task_done()

            except Exception as e:
                if self.running and not isinstance(e, Empty):  # Not shutting down and not a timeout error
                    logger.error(f"Output thread error: {e}")
    
    def stop_output_thread(self):
        """Stop the worker thread for data output."""
        self.running = False
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(2.0)  # 最大2秒待機