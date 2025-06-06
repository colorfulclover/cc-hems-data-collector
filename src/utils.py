# src/utils.py
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def parse_echonet_frame(frame_hex_str: str) -> dict | None:
    """
    ECHONET Liteのフレーム(16進数文字列)を辞書にパースする。
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
    """ECHONET Liteの応答から指定したプロパティのEDT値を抽出する"""
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
    """積算電力量の解析"""
    if not hex_value:
        return None
    try:
        value = int(hex_value, 16) / 10.0  # 単位はkWh
        return value
    except (ValueError, TypeError):
        logger.error(f"積算電力量の解析エラー: {hex_value}")
        return None

def parse_instant_power(hex_value):
    """瞬時電力の解析"""
    if not hex_value:
        return None
    try:
        value = int(hex_value, 16)  # 単位はW
        return value
    except (ValueError, TypeError):
        logger.error(f"瞬時電力の解析エラー: {hex_value}")
        return None

def parse_current_value(hex_value):
    """瞬時電流の解析"""
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
    """現在のタイムスタンプを取得"""
    return datetime.now().isoformat()