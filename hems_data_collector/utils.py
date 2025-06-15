# src/utils.py
"""Data analysis and utility functions.

Provides helper functions used throughout the project,
including ECHONET Lite frame analysis, power data conversions,
and timestamp generation.
"""
import logging
from datetime import datetime, timezone, timedelta
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from hems_data_collector.config import LOCAL_TIMEZONE

logger = logging.getLogger(__name__)

def get_timezone():
    if LOCAL_TIMEZONE:
        try:
            return ZoneInfo(LOCAL_TIMEZONE)
        except ZoneInfoNotFoundError:
            logger.error(f"Specified timezone is invalid: {LOCAL_TIMEZONE}. Using UTC.")
            return timezone.utc
    else:
        return timezone.utc

def parse_echonet_frame(frame_hex_str: str) -> dict | None:
    """Parse ECHONET Lite frame (hexadecimal string) into a dictionary.

    Args:
        frame_hex_str (str): ECHONET Lite frame (hexadecimal string) to be parsed.

    Returns:
        dict | None: Dictionary containing parsed frame information.
            Returns None if parsing fails.
            Dictionary structure:
            {
                'EHD': str, 'TID': str, 'SEOJ': str, 'DEOJ': str,
                'ESV': str, 'OPC': int,
                'properties': [{'EPC': str, 'PDC': int, 'EDT': str}, ...]
            }
    """
    if not frame_hex_str or len(frame_hex_str) < 24: # EHD+TID+SEOJ+DEOJ+ESV+OPC = 12 bytes = 24 chars
        logger.warning(f"Too short or invalid ECHONET Lite frame: {frame_hex_str}")
        return None

    try:
        data = {
            'EHD': frame_hex_str[0:4],
            'TID': frame_hex_str[4:8],
            'SEOJ': frame_hex_str[8:14],
            'DEOJ': frame_hex_str[14:20],
            'ESV': frame_hex_str[20:22],
            'OPC': int(frame_hex_str[22:24], 16),
            'properties': []
        }

        if data['EHD'] != '1081':
            logger.warning(f"Invalid ECHONET Lite header: {data['EHD']}")
            return None

        # Check if ESV is an error response (SNA)
        if data['ESV'].startswith('5'):
             logger.warning(f"ESV indicates error response (SNA): {data['ESV']}. Frame: {frame_hex_str}")

        # OPCに基づいてプロパティをパース
        current_pos = 24
        for _ in range(data['OPC']):
            if len(frame_hex_str) < current_pos + 4: # EPC(2) + PDC(2)
                logger.error("Frame is too short to parse properties.")
                break

            epc = frame_hex_str[current_pos : current_pos+2]
            pdc = int(frame_hex_str[current_pos+2 : current_pos+4], 16)

            edt_start = current_pos + 4
            edt_end = edt_start + (pdc * 2)

            if len(frame_hex_str) < edt_end:
                logger.error(f"Frame is too short to parse EDT. EPC: {epc}, PDC: {pdc}")
                break
            
            edt = frame_hex_str[edt_start:edt_end]
            
            data['properties'].append({
                'EPC': epc.upper(),
                'PDC': pdc,
                'EDT': edt.upper()
            })
            current_pos = edt_end
        
        return data

    except (ValueError, IndexError) as e:
        logger.error(f"Error occurred while parsing ECHONET Lite frame: {e}. Frame: {frame_hex_str}")
        return None

def parse_echonet_response(response, property_code):
    """Extract the EDT value of the specified property from an ECHONET Lite response.

    Args:
        response (str): ECHONET Lite frame (hexadecimal string) received from ERXUDP.
        property_code (str): EPC code (hexadecimal string) of the property to be extracted.

    Returns:
        str | None: EDT (data) string of the found property.
            None if not found or in case of an error.
    """
    if not response:
        return None
    
    parsed_frame = parse_echonet_frame(response)
    
    if not parsed_frame:
        return None

    # Verify it is a response (Get_Res)
    if parsed_frame['ESV'] != '72':
        logger.warning(f"Not the expected response (ESV=72): ESV={parsed_frame['ESV']}")
        return None

    # Check if the requested property is included
    for prop in parsed_frame['properties']:
        if prop['EPC'] == property_code.upper():
            logger.debug(f"Found value (EDT) for property {property_code}: {prop['EDT']}")
            return prop['EDT']

    logger.warning(f"Requested property {property_code} not found in response.")
    return None

def parse_cumulative_power(hex_value, multiplier=1.0):
    """Convert cumulative power hexadecimal value to kWh as floating point with the specified multiplier.

    Args:
        hex_value (str): Hexadecimal string representing cumulative power.
        multiplier (float, optional): Multiplier to apply. Defaults to 1.0.

    Returns:
        float | None: Converted value in kWh. None in case of error.
    """
    if not hex_value:
        return None
    try:
        value = int(hex_value, 16) * multiplier
        # 乗数に基づいて小数点以下の桁数を決定し、丸める
        if multiplier < 1:
            # 例: multiplier=0.1 -> decimals=1, 0.01 -> 2
            decimals = -int(math.log10(multiplier))
            value = round(value, decimals)
        return value
    except (ValueError, TypeError):
        logger.error(f"Error parsing cumulative power: {hex_value}")
        return None

POWER_UNITS = {
    "00": 1.0,        # 1 kWh
    "01": 0.1,      # 0.1 kWh
    "02": 0.01,     # 0.01 kWh
    "03": 0.001,    # 0.001 kWh
    "04": 0.0001,   # 0.0001 kWh
    "0A": 10.0,       # 10 kWh
    "0B": 100.0,      # 100 kWh
    "0C": 1000.0,     # 1000 kWh
    "0D": 10000.0,    # 10000 kWh
}

def parse_power_unit(hex_value: str) -> float:
    """Convert cumulative power unit hexadecimal value to multiplier (float).

    Args:
        hex_value (str): Hexadecimal string representing the power unit.

    Returns:
        float: Converted multiplier. Returns 1.0 if unknown.
    """
    if not hex_value or hex_value.upper() not in POWER_UNITS:
        logger.warning(f"Unknown power unit code: {hex_value}. Using default multiplier (1.0).")
        return 1.0
    return POWER_UNITS[hex_value.upper()]

def get_current_timestamp():
    """Get the current time as an ISO 8601 formatted timestamp string based on UTC.

    Returns:
        str: ISO 8601 formatted timestamp string based on UTC.
    """
    return datetime.now(timezone.utc).isoformat()

def _parse_signed_hex(hex_str: str) -> int:
    """Convert a two's complement hexadecimal string to a signed integer.

    Args:
        hex_str (str): Hexadecimal string to convert.

    Returns:
        int: Converted signed integer.
    """
    value = int(hex_str, 16)
    bits = len(hex_str) * 4
    # If the most significant bit is 1 (negative number)
    if (value & (1 << (bits - 1))) != 0:
        # Calculate two's complement and convert to negative
        value = value - (1 << bits)
    return value

def parse_instant_power(hex_value):
    """Convert instantaneous power hexadecimal value to integer in watts.

    Interpreted as a 4-byte signed integer.

    Args:
        hex_value (str): Hexadecimal string representing instantaneous power (4 bytes/8 characters).

    Returns:
        int | None: Converted value in watts. None in case of error.
    """
    if not hex_value or len(hex_value) != 8:
        logger.warning(f"Invalid instantaneous power value (not 4 bytes): {hex_value}")
        return None
    try:
        # Interpret as 4-byte signed integer
        value = _parse_signed_hex(hex_value)
        return value
    except (ValueError, TypeError):
        logger.error(f"Error parsing instantaneous power: {hex_value}")
        return None

def parse_current_value(hex_value):
    """Convert instantaneous current hexadecimal value to a dictionary with values in amperes.

    The return format is always consistent:
    - `current_a`: Representative current (A). For single-phase, it's the R-phase value; for three-phase, it's the sum of R and T phases.
    - `current_r_a`: R-phase current (A).
    - `current_t_a`: T-phase current (A). None for single-phase.

    Args:
        hex_value (str): Hexadecimal string representing instantaneous current.

    Returns:
        dict | None: Dictionary containing converted current values. None in case of error.
    """
    if not hex_value:
        return None
    try:
        # Three-phase 3-wire or single-phase 2-wire (4 bytes = 8 characters)
        if len(hex_value) == 8:
            r_phase_hex = hex_value[0:4]
            t_phase_hex = hex_value[4:8]

            # If T-phase is 0x7FFE (undefined), treat as single-phase 2-wire
            if t_phase_hex.upper() == '7FFE':
                current_r = _parse_signed_hex(r_phase_hex) / 10.0
                return {
                    'current_a': round(current_r, 1),
                    'current_r_a': round(current_r, 1),
                    'current_t_a': None
                }
            else:
                # Normal three-phase 3-wire
                current_r = _parse_signed_hex(r_phase_hex) / 10.0
                current_t = _parse_signed_hex(t_phase_hex) / 10.0
                return {
                    'current_a': round(current_r + current_t, 1),
                    'current_r_a': round(current_r, 1),
                    'current_t_a': round(current_t, 1)
                }

        # (Kept for backward compatibility, but normally expected to be sent as 4 bytes)
        elif len(hex_value) == 4:
            current_r = _parse_signed_hex(hex_value) / 10.0
            return {
                'current_a': round(current_r, 1),
                'current_r_a': round(current_r, 1),
                'current_t_a': None
            }

        else:
            logger.warning(f"Unexpected instantaneous current data length (length: {len(hex_value)}): {hex_value}")
            return None
            
    except (ValueError, TypeError):
        logger.error(f"Error parsing instantaneous current: {hex_value}")
        return None

def parse_historical_power(hex_value, multiplier=1.0):
    """Convert regular cumulative power (EA) hexadecimal value to a dictionary.

    Args:
        hex_value (str): Hexadecimal string representing regular cumulative power (11 bytes/22 characters).
        multiplier (float, optional): Multiplier to apply to the power value. Defaults to 1.0.

    Returns:
        dict | None: Dictionary containing converted data.
            {'historical_timestamp': str, 'historical_cumulative_power_kwh': float}
            None in case of error.
    """
    if not hex_value or len(hex_value) != 22:
        logger.warning(f"Invalid regular cumulative power data length (not 11 bytes): {hex_value}")
        return None
    try:
        year = int(hex_value[0:4], 16)
        month = int(hex_value[4:6], 16)
        day = int(hex_value[6:8], 16)
        hour = int(hex_value[8:10], 16)
        minute = int(hex_value[10:12], 16)
        second = int(hex_value[12:14], 16)
        
        power_value_hex = hex_value[14:22]

        try:
            # Create datetime object without timezone information
            naive_dt = datetime(year, month, day, hour, minute, second)

            # Add configured timezone information
            tz = get_timezone()
            local_dt = naive_dt.replace(tzinfo=tz)

            # Convert to UTC and generate ISO format string
            historical_timestamp = local_dt.astimezone(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"Error occurred during timestamp timezone conversion: {e}")
            # If an error occurs, use timestamp without timezone information
            historical_timestamp = datetime(year, month, day, hour, minute, second).isoformat()

        # Calculate cumulative power
        historical_power_kwh = int(power_value_hex, 16) * multiplier

        # Round digits
        if multiplier < 1:
            decimals = -int(math.log10(multiplier))
            historical_power_kwh = round(historical_power_kwh, decimals)

        return {
            'historical_timestamp': historical_timestamp,
            'historical_cumulative_power_kwh': historical_power_kwh
        }
        
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing regular cumulative power: {e}, Data: {hex_value}")
        return None

def parse_cumulative_power_history(today_edt, yesterday_edt=None, multiplier=1.0):
    """
    Analyze cumulative power measurement history 1 (EDT: 0xE2) and calculate power consumption over the last 30 minutes.
    If calculation is not possible with today's data, consider yesterday's data.

    Args:
        today_edt (str): Today's (00) 0xE2 response data.
        yesterday_edt (str, optional): Yesterday's (01) 0xE2 response data. Defaults to None.
        multiplier (float): Unit multiplier to apply to cumulative power.

    Returns:
        dict | None: Dictionary containing calculation results, or None if calculation is not possible.
    """
    def _extract_readings(edt):
        """Internal function to extract a list of 48 cumulative values from the EDT of E2"""
        if not edt or len(edt) < 388:
            logger.warning(f"Invalid cumulative power history (E2) data length: {len(edt) if edt else 0} characters")
            return []

        # Skip the first 2 bytes (4 characters) which represent collection date
        values_hex = edt[4:]
        readings = []
        logger.debug("--- Cumulative power history (E2) data analysis start ---")
        for i in range(48):
            val_hex = values_hex[i*8 : (i+1)*8].upper()

            hour = (i * 30) // 60
            minute = (i * 30) % 60

            if val_hex == 'FFFFFFFE':
                readings.append(None)
                logger.debug(f"  Slot {i:02d} ({hour:02d}:{minute:02d}): RAW={val_hex} -> Interpretation=No data(None)")
            else:
                try:
                    val_int = int(val_hex, 16)
                    readings.append(val_int)
                    logger.debug(f"  Slot {i:02d} ({hour:02d}:{minute:02d}): RAW={val_hex} -> Interpretation={val_int}")
                except (ValueError, TypeError):
                    readings.append(None)
                    logger.warning(f"  Slot {i:02d} ({hour:02d}:{minute:02d}): RAW={val_hex} -> Interpretation error(None)")

        logger.debug("--- Cumulative power history (E2) data analysis end ---")
        return readings

    try:
        today_readings = _extract_readings(today_edt)
        
        # Flag to indicate whether yesterday's data is provided
        is_yesterday_data_present = yesterday_edt is not None and len(yesterday_edt) >= 388

        if is_yesterday_data_present:
            yesterday_readings = _extract_readings(yesterday_edt)
            combined_readings = yesterday_readings + today_readings
        else:
            combined_readings = today_readings

        latest_value = None
        previous_value = None
        latest_idx_abs = -1
        previous_idx_abs = -1

        for i in range(len(combined_readings) - 1, -1, -1):
            if combined_readings[i] is not None:
                if latest_value is None:
                    latest_value = combined_readings[i]
                    latest_idx_abs = i
                else:
                    previous_value = combined_readings[i]
                    previous_idx_abs = i
                    break

        if latest_value is None or previous_value is None:
            logger.info("Insufficient data points for 30-minute power consumption calculation (less than 2 valid history entries)")
            return None

        consumption_kwh = (latest_value - previous_value) * multiplier
        
        def _get_timestamp_from_index(idx, is_yesterday_present):
            if is_yesterday_present:
                is_today_calc = idx >= 48
            else:
                is_today_calc = True
            
            if is_yesterday_present and is_today_calc:
                idx_rel = idx - 48
            else:
                idx_rel = idx

            hour_calc = (idx_rel * 30) // 60
            minute_calc = (idx_rel * 30) % 60
            
            date_calc = datetime.now(get_timezone()).date()
            if not is_today_calc:
                date_calc -= timedelta(days=1)
                
            ts = datetime(date_calc.year, date_calc.month, date_calc.day, hour_calc, minute_calc, tzinfo=get_timezone())
            return ts.isoformat()

        latest_ts = _get_timestamp_from_index(latest_idx_abs, is_yesterday_data_present)
        previous_ts = _get_timestamp_from_index(previous_idx_abs, is_yesterday_data_present)
        
        logger.debug("--- 30-minute power consumption calculation ---")
        logger.debug(f"  Latest value (time: {latest_ts}): {latest_value} (raw)")
        logger.debug(f"  Previous value (time: {previous_ts}): {previous_value} (raw)")
        logger.debug(f"  Multiplier: {multiplier}")
        logger.debug(f"  Calculation result: {consumption_kwh} kWh")

        # Modify the is_today determination logic
        if is_yesterday_data_present:
            is_today = latest_idx_abs >= 48
        else:
            is_today = True # If there's no yesterday's data, the found index must be today's

        # Calculate relative index
        if is_yesterday_data_present and is_today:
            latest_idx_rel = latest_idx_abs - 48
        else:
            latest_idx_rel = latest_idx_abs
        
        hour = (latest_idx_rel * 30) // 60
        minute = (latest_idx_rel * 30) % 60
        
        target_date = datetime.now(get_timezone()).date()
        if not is_today:
            target_date -= timedelta(days=1)
            
        naive_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
        timestamp_str = naive_dt.replace(tzinfo=get_timezone()).astimezone(timezone.utc).isoformat()
        
        if multiplier < 1:
            decimals = -int(math.log10(multiplier))
            consumption_kwh = round(consumption_kwh, decimals)
                
        return {
            'recent_30min_consumption_kwh': consumption_kwh,
            'recent_30min_timestamp': timestamp_str
        }
    except (ValueError, TypeError, IndexError) as e:
        logger.error(f"Error parsing cumulative power history (E2): {e}")
        return None