# src/utils.py
"""データ解析とユーティリティ関数。

ECHONET Liteのフレーム解析、各種電力データの数値変換、
タイムスタンプ生成など、プロジェクト全体で利用される
ヘルパー関数を提供します。
"""
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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

def parse_cumulative_power(hex_value):
    """積算電力量の16進数値をkWh単位の浮動小数点数に変換します。

    Args:
        hex_value (str): 積算電力量を示す16進数文字列。

    Returns:
        float | None: 変換後のkWh値。エラーの場合はNone。
    """
    if not hex_value:
        return None
    try:
        value = int(hex_value, 16) / 10.0  # 単位はkWh
        return value
    except (ValueError, TypeError):
        logger.error(f"積算電力量の解析エラー: {hex_value}")
        return None

def parse_instant_power(hex_value):
    """瞬時電力の16進数値をW単位の整数に変換します。

    Args:
        hex_value (str): 瞬時電力を示す16進数文字列。

    Returns:
        int | None: 変換後のW値。エラーの場合はNone。
    """
    if not hex_value:
        return None
    try:
        value = int(hex_value, 16)  # 単位はW
        return value
    except (ValueError, TypeError):
        logger.error(f"瞬時電力の解析エラー: {hex_value}")
        return None

def parse_current_value(hex_value):
    """瞬時電流の16進数値をA単位の辞書に変換します。

    単相の場合は {'current': float}、三相の場合は {'current_r': float, 'current_t': float}
    の形式で返します。

    Args:
        hex_value (str): 瞬時電流を示す16進数文字列。

    Returns:
        dict | None: 変換後の電流値を含む辞書。エラーの場合はNone。
    """
    if not hex_value:
        return None
    try:
        # 単相の場合
        if len(hex_value) == 2:
            current_value = int(hex_value, 16) / 10.0  # 単位はA
            return {'current': current_value}
        # 三相の場合
        elif len(hex_value) >= 4:
            r_phase = int(hex_value[0:2], 16) / 10.0
            t_phase = int(hex_value[2:4], 16) / 10.0
            return {'current_r': r_phase, 'current_t': t_phase}
        return None
    except (ValueError, TypeError):
        logger.error(f"瞬時電流の解析エラー: {hex_value}")
        return None

def get_current_timestamp():
    """現在の時刻をISO 8601形式のタイムスタンプ文字列として取得します。

    Returns:
        str: ISO 8601形式のタイムスタンプ文字列。
    """
    return datetime.now().isoformat()