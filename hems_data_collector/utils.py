# src/utils.py
"""データ解析とユーティリティ関数。

ECHONET Liteのフレーム解析、各種電力データの数値変換、
タイムスタンプ生成など、プロジェクト全体で利用される
ヘルパー関数を提供します。
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
            logger.error(f"指定されたタイムゾーンが無効です: {LOCAL_TIMEZONE}. UTCを使用します。")
            return timezone.utc
    else:
        return timezone.utc

def parse_echonet_frame(frame_hex_str: str) -> dict | None:
    """ECHONET Liteのフレーム(16進数文字列)を辞書にパースします。

    Args:
        frame_hex_str (str): パース対象のECHONET Liteフレーム（16進数文字列）。

    Returns:
        dict | None: パースされたフレーム情報を格納した辞書。
            パースに失敗した場合はNone。
            辞書の構造:
            {
                'EHD': str, 'TID': str, 'SEOJ': str, 'DEOJ': str,
                'ESV': str, 'OPC': int,
                'properties': [{'EPC': str, 'PDC': int, 'EDT': str}, ...]
            }
    """
    if not frame_hex_str or len(frame_hex_str) < 24: # EHD+TID+SEOJ+DEOJ+ESV+OPC = 12 bytes = 24 chars
        logger.warning(f"短すぎる、または不正なECHONET Liteフレームです: {frame_hex_str}")
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
            logger.warning(f"不正なECHONET Liteヘッダです: {data['EHD']}")
            return None

        # ESVがエラー応答(SNA)かチェック
        if data['ESV'].startswith('5'):
             logger.warning(f"ESVがエラー応答(SNA)を示しています: {data['ESV']}. フレーム: {frame_hex_str}")

        # OPCに基づいてプロパティをパース
        current_pos = 24
        for _ in range(data['OPC']):
            if len(frame_hex_str) < current_pos + 4: # EPC(2) + PDC(2)
                logger.error("フレームが短いためプロパティをパースできません。")
                break
            
            epc = frame_hex_str[current_pos : current_pos+2]
            pdc = int(frame_hex_str[current_pos+2 : current_pos+4], 16)
            
            edt_start = current_pos + 4
            edt_end = edt_start + (pdc * 2)

            if len(frame_hex_str) < edt_end:
                logger.error(f"フレームが短いためEDTをパースできません。EPC: {epc}, PDC: {pdc}")
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
        logger.error(f"ECHONET Liteフレームのパース中にエラーが発生しました: {e}。フレーム: {frame_hex_str}")
        return None

def parse_echonet_response(response, property_code):
    """ECHONET Liteの応答から指定したプロパティのEDT値を抽出します。

    Args:
        response (str): ERXUDPから受信したECHONET Liteフレーム（16進数文字列）。
        property_code (str): 抽出したいプロパティのEPCコード（16進数文字列）。

    Returns:
        str | None: 見つかったプロパティのEDT（データ）部分の文字列。
            見つからない、またはエラーの場合はNone。
    """
    if not response:
        return None
    
    parsed_frame = parse_echonet_frame(response)
    
    if not parsed_frame:
        return None

    # 応答(Get_Res)か確認
    if parsed_frame['ESV'] != '72':
        logger.warning(f"期待する応答(ESV=72)ではありませんでした: ESV={parsed_frame['ESV']}")
        return None

    # 要求したプロパティが含まれているか探す
    for prop in parsed_frame['properties']:
        if prop['EPC'] == property_code.upper():
            logger.debug(f"プロパティ {property_code} の値(EDT)が見つかりました: {prop['EDT']}")
            return prop['EDT']
    
    logger.warning(f"応答内に要求したプロパティ {property_code} が見つかりませんでした。")
    return None

def parse_cumulative_power(hex_value, multiplier=1.0):
    """積算電力量の16進数値を指定された倍率を適用してkWh単位の浮動小数点数に変換します。

    Args:
        hex_value (str): 積算電力量を示す16進数文字列。
        multiplier (float, optional): 適用する倍率。Defaults to 1.0.

    Returns:
        float | None: 変換後のkWh値。エラーの場合はNone。
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
        logger.error(f"積算電力量の解析エラー: {hex_value}")
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
    """積算電力量単位の16進数値を倍率(float)に変換します。

    Args:
        hex_value (str): 積算電力量単位を示す16進数文字列。

    Returns:
        float: 変換後の倍率。不明な場合は1.0を返す。
    """
    if not hex_value or hex_value.upper() not in POWER_UNITS:
        logger.warning(f"不明な電力単位コードです: {hex_value}。デフォルトの倍率(1.0)を使用します。")
        return 1.0
    return POWER_UNITS[hex_value.upper()]

def get_current_timestamp():
    """現在の時刻をUTC基準のISO 8601形式タイムスタンプ文字列として取得します。

    Returns:
        str: UTC基準のISO 8601形式のタイムスタンプ文字列。
    """
    return datetime.now(timezone.utc).isoformat()

def _parse_signed_hex(hex_str: str) -> int:
    """2の補数表現の16進数文字列を符号付き整数に変換します。
    
    Args:
        hex_str (str): 変換対象の16進数文字列。
    
    Returns:
        int: 変換後の符号付き整数。
    """
    value = int(hex_str, 16)
    bits = len(hex_str) * 4
    # 最上位ビットが1の場合（負数）
    if (value & (1 << (bits - 1))) != 0:
        # 2の補数を計算して負数に変換
        value = value - (1 << bits)
    return value

def parse_instant_power(hex_value):
    """瞬時電力の16進数値をW単位の整数に変換します。
    
    4バイトの符号付き整数として解釈します。

    Args:
        hex_value (str): 瞬時電力を示す16進数文字列 (4バイト/8文字)。

    Returns:
        int | None: 変換後のW値。エラーの場合はNone。
    """
    if not hex_value or len(hex_value) != 8:
        logger.warning(f"瞬時電力の値が不正です(4バイトではありません): {hex_value}")
        return None
    try:
        # 4バイト符号付き整数として解釈
        value = _parse_signed_hex(hex_value)
        return value
    except (ValueError, TypeError):
        logger.error(f"瞬時電力の解析エラー: {hex_value}")
        return None

def parse_current_value(hex_value):
    """瞬時電流の16進数値をA単位の辞書に変換します。

    2バイトの符号付き整数として各値を解釈します。
    R相とT相で構成され、単相2線式の場合はT相に0x7FFEがセットされます。
    
    - 三相3線式: {'current_r': float, 'current_t': float}
    - 単相2線式: {'current': float}

    Args:
        hex_value (str): 瞬時電流を示す16進数文字列。

    Returns:
        dict | None: 変換後の電流値を含む辞書。エラーの場合はNone。
    """
    if not hex_value:
        return None
    try:
        # 三相3線式 or 単相2線式 (4バイト = 8文字)
        if len(hex_value) == 8:
            r_phase_hex = hex_value[0:4]
            t_phase_hex = hex_value[4:8]

            # T相が 0x7FFE (未定義) の場合は単相2線式として扱う
            if t_phase_hex.upper() == '7FFE':
                current_value = _parse_signed_hex(r_phase_hex) / 10.0
                return {'current': round(current_value, 1)}
            else:
                # 通常の三相3線式
                r_phase = _parse_signed_hex(r_phase_hex) / 10.0
                t_phase = _parse_signed_hex(t_phase_hex) / 10.0
                return {'current_r': round(r_phase, 1), 'current_t': round(t_phase, 1)}
        
        # (下位互換性のため残すが、通常は4バイトで送られる想定)
        elif len(hex_value) == 4:
            current_value = _parse_signed_hex(hex_value) / 10.0
            return {'current': round(current_value, 1)}
        
        else:
            logger.warning(f"瞬時電流のデータ長が想定外です (長さ: {len(hex_value)}): {hex_value}")
            return None
            
    except (ValueError, TypeError):
        logger.error(f"瞬時電流の解析エラー: {hex_value}")
        return None

def parse_historical_power(hex_value, multiplier=1.0):
    """定時積算電力量(EA)の16進数値を辞書に変換します。

    Args:
        hex_value (str): 定時積算電力量を示す16進数文字列(11バイト/22文字)。
        multiplier (float, optional): 積算電力量に適用する倍率。Defaults to 1.0.

    Returns:
        dict | None: 変換後のデータを含む辞書。
            {'historical_timestamp': str, 'historical_cumulative_power_kwh': float}
            エラーの場合はNone。
    """
    if not hex_value or len(hex_value) != 22:
        logger.warning(f"定時積算電力量データ長が不正です(11バイトではありません): {hex_value}")
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
            # タイムゾーン情報のないdatetimeオブジェクトを作成
            naive_dt = datetime(year, month, day, hour, minute, second)
            
            # 設定されたタイムゾーン情報を付与
            tz = get_timezone()
            local_dt = naive_dt.replace(tzinfo=tz)
            
            # UTCに変換してISOフォーマット文字列を生成
            historical_timestamp = local_dt.astimezone(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"タイムスタンプのタイムゾーン変換中にエラーが発生しました: {e}")
            # エラーが発生した場合は、タイムゾーン情報なしのタイムスタンプを使用する
            historical_timestamp = datetime(year, month, day, hour, minute, second).isoformat()

        # 積算電力量を計算
        historical_power_kwh = int(power_value_hex, 16) * multiplier
        
        # 桁丸め
        if multiplier < 1:
            decimals = -int(math.log10(multiplier))
            historical_power_kwh = round(historical_power_kwh, decimals)

        return {
            'historical_timestamp': historical_timestamp,
            'historical_cumulative_power_kwh': historical_power_kwh
        }
        
    except (ValueError, TypeError) as e:
        logger.error(f"定時積算電力量の解析エラー: {e}, データ: {hex_value}")
        return None

def parse_cumulative_power_history(today_edt, yesterday_edt=None, multiplier=1.0):
    """
    積算電力量計測値履歴1 (EDT: 0xE2) を解析し、直近30分間の消費電力量を計算する。
    本日分のデータで計算できない場合、昨日分のデータを考慮する。

    Args:
        today_edt (str): 本日(00)の0xE2応答データ。
        yesterday_edt (str, optional): 昨日(01)の0xE2応答データ。Defaults to None.
        multiplier (float): 積算電力量に適用する単位倍率。

    Returns:
        dict | None: 計算結果を含む辞書、または計算不可の場合None。
    """
    def _extract_readings(edt):
        if not edt or len(edt) < 388:
            logger.warning(f"積算電力量履歴(E2)のデータ長が不正です: {len(edt) if edt else 0}文字")
            return []
        
        values_hex = edt[4:] # 収集日(2byte)をスキップ
        readings = []
        for i in range(48):
            val_hex = values_hex[i*8 : (i+1)*8]
            if val_hex.upper() == 'FFFFFFFE':
                readings.append(None)
            else:
                readings.append(int(val_hex, 16))
        return readings

    try:
        today_readings = _extract_readings(today_edt)
        
        # 昨日データが提供されているかどうかのフラグ
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
            logger.info("30分消費電力の計算に必要なデータポイントが不足しています（有効な履歴が2つ未満）")
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
        
        logger.debug(f"30分消費電力計算デバッグ:")
        logger.debug(f"  - 最新値 (時刻: {latest_ts}): {latest_value} (raw)")
        logger.debug(f"  - 前回値 (時刻: {previous_ts}): {previous_value} (raw)")
        logger.debug(f"  - 乗数: {multiplier}")
        logger.debug(f"  - 計算結果: {consumption_kwh} kWh")

        # is_today の判定ロジックを修正
        if is_yesterday_data_present:
            is_today = latest_idx_abs >= 48
        else:
            is_today = True # 昨日データがないなら、見つかったインデックスは必ず今日のもの

        # 相対インデックスの計算
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
        logger.error(f"積算電力量履歴(E2)の解析エラー: {e}")
        return None