# src/utils.py
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def parse_echonet_response(response, property_code):
    """ECHONET Liteの応答からプロパティ値を抽出"""
    if not response:
        return None
    
    # プロパティ値を正規表現で抽出
    pattern = r'1081......0288010102880172......{}..(.*?)(?:\r|\n|$)'.format(property_code)
    match = re.search(pattern, response, re.MULTILINE)
    
    if not match:
        return None
        
    return match.group(1)

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