# src/serial_client.py
import serial
import time
import re
import logging
import traceback
from queue import Queue
import threading

from src.config import (
    SERIAL_PORT, SERIAL_RATE, B_ROUTE_ID, B_ROUTE_PASSWORD, 
    METER_CHANNEL, METER_IPV6, ECHONET_PROPERTY_CODES
)
from src.utils import (
    parse_echonet_response, parse_cumulative_power,
    parse_instant_power, parse_current_value, get_current_timestamp
)

logger = logging.getLogger(__name__)

class SmartMeterClient:
    def __init__(self, port=SERIAL_PORT, baudrate=SERIAL_RATE, output_handlers=None):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.mac_address = None
        self.output_handlers = output_handlers or []
        self.data_queue = Queue()
        self.output_thread = None
        self.running = False
    
    def open_connection(self):
        """シリアルポートを開く"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=10  # 読み取りタイムアウト（秒）
            )
            logger.info(f"シリアルポート {self.port} を開きました（ボーレート: {self.baudrate}）")
            return True
        except Exception as e:
            logger.error(f"シリアルポートを開く際にエラーが発生しました: {e}")
            return False
    
    def close_connection(self):
        """シリアルポートを閉じる"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("シリアルポートを閉じました")
    
    def send_command(self, command, wait_time=1, expected_response=None, timeout=10):
        """コマンドを送信し、応答を待機"""
        if not self.ser or not self.ser.is_open:
            logger.error("シリアルポートが開いていません")
            return None
        
        # コマンドの末尾に改行を追加（必要な場合）
        if not command.endswith('\r\n'):
            command += '\r\n'
        
        # コマンド送信
        logger.debug(f"送信: {command.strip()}")
        self.ser.write(command.encode('utf-8'))
        self.ser.flush()
        
        # 応答待機
        time.sleep(wait_time)
        
        # 応答の読み取り
        response = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                logger.debug(f"受信: {line}")
                response += line + "\n"
                
                # 期待する応答が含まれているか確認
                if expected_response and expected_response in line:
                    return response
                
                # ERRORが含まれている場合
                if "ERROR" in line:
                    logger.error(f"エラー応答を受信: {line}")
                    return response
            
            else:
                time.sleep(0.1)  # 少し待機
        
        return response
    
    def initialize(self):
        """BP35A1の初期化とスマートメーターへの接続"""
        if not self.open_connection():
            return False
        
        # スキャンモードをアクティブに設定
        logger.info("BP35A1の初期化を開始...")
        
        # バージョン情報の取得
        version = self.send_command("SKVER")
        logger.info(f"BP35A1バージョン: {version.strip() if version else 'Unknown'}")
        
        # アクティブスキャンモードの設定
        self.send_command("SKSREG S2 2")
        
        # Bルート認証情報の設定
        logger.info("Bルート認証情報を設定...")
        self.send_command(f"SKSETPWD C {B_ROUTE_PASSWORD}")
        self.send_command(f"SKSETRBID {B_ROUTE_ID}")
        
        # チャンネルの設定
        logger.info(f"チャンネルを {METER_CHANNEL} に設定...")
        self.send_command(f"SKSREG S2 {METER_CHANNEL}")
        
        # PANスキャンの実行
        logger.info(f"PANスキャンを実行中...")
        response = self.send_command(f"SKSCAN 2 FFFFFFFF {METER_CHANNEL}", wait_time=5)
        
        # スキャン結果からPANアドレスを取得
        pan_desc_match = re.search(r'EPANDESC\s+([0-9A-F]{16})', response, re.MULTILINE)
        if not pan_desc_match:
            logger.error("PANデスクリプタが見つかりませんでした")
            return False
            
        pan_addr = pan_desc_match.group(1)
        logger.info(f"見つかったPANアドレス: {pan_addr}")
        
        # チャンネルを再設定
        channel_match = re.search(r'Channel:([0-9A-F]{2})', response)
        if channel_match:
            channel = channel_match.group(1)
            logger.info(f"チャンネルを {channel} に設定...")
            self.send_command(f"SKSREG S2 {channel}")
        
        # PANIDを取得
        pan_id_match = re.search(r'Pan ID:([0-9A-F]{4})', response)
        if pan_id_match:
            pan_id = pan_id_match.group(1)
            logger.info(f"PANID: {pan_id}")
        
        # PANに接続
        logger.info("PANに接続中...")
        self.send_command(f"SKJOIN {pan_addr}")
        
        # 接続完了を待機
        for _ in range(20):  # 最大20秒待機
            time.sleep(1)
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                logger.debug(f"受信: {line}")
                
                if "EVENT 25" in line:  # 接続成功イベント
                    logger.info("スマートメーターに接続しました")
                    self.connected = True
                    return True
        
        logger.error("スマートメーターへの接続に失敗しました")
        return False
    
    def get_property(self, property_code, transaction_id=1):
        """指定したプロパティ値を取得"""
        if not self.connected:
            logger.error("スマートメーターに接続されていません")
            return None
            
        # ECHONET Lite要求の作成
        # データ長は64バイト（実際の長さに応じて調整）
        command = f"SKSENDTO 1 {METER_IPV6} 0E1A 1 0040 "
        
        # ECHONET Lite電文の作成
        # 10 81: EHD（ECHONET Lite ヘッダ）
        # xx xx: TID（トランザクションID）
        # 05 FF 01: SEOJ（送信元ECHONET Liteオブジェクト）
        # 02 88 01: DEOJ（宛先ECHONET Liteオブジェクト - 低圧スマート電力量メータ）
        # 62: ESV（Get）
        # 01: OPC（処理プロパティ数）
        # xx: EPC（取得するプロパティ）
        # 00: PDC（プロパティデータカウンタ）
        tid_hex = format(transaction_id, '04x')
        echonet_frame = f"1081{tid_hex}05FF010288016201{property_code}00"
        
        # コマンドを送信
        response = self.send_command(command + echonet_frame, wait_time=2)
        
        return response
    
    def get_meter_data(self):
        """スマートメーターから各種データを取得"""
        if not self.connected:
            logger.error("スマートメーターに接続されていません")
            return None
        
        data = {}
        data['timestamp'] = get_current_timestamp()
        
        try:
            # 積算電力量計測値の取得
            logger.info("積算電力量を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'], 1)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'])
            if hex_value:
                power_value = parse_cumulative_power(hex_value)
                if power_value is not None:
                    data['cumulative_power'] = power_value
                    logger.info(f"積算電力量: {power_value} kWh")
            
            # 瞬時電力計測値の取得
            logger.info("瞬時電力を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['INSTANT_POWER'], 2)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['INSTANT_POWER'])
            if hex_value:
                power_value = parse_instant_power(hex_value)
                if power_value is not None:
                    data['instant_power'] = power_value
                    logger.info(f"瞬時電力: {power_value} W")
            
            # 瞬時電流計測値の取得
            logger.info("瞬時電流を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CURRENT_VALUE'], 3)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CURRENT_VALUE'])
            if hex_value:
                current_data = parse_current_value(hex_value)
                if current_data:
                    data.update(current_data)
                    if 'current' in current_data:
                        logger.info(f"瞬時電流: {current_data['current']} A")
                    else:
                        logger.info(f"瞬時電流: R相={current_data['current_r']}A, T相={current_data['current_t']}A")
            
            return data if len(data) > 1 else None  # タイムスタンプ以外のデータがある場合のみ返す
            
        except Exception as e:
            logger.error(f"データ取得中にエラーが発生しました: {e}")
            traceback.print_exc()
            return None

    def start_output_thread(self):
        """出力スレッドを開始"""
        self.running = True
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.daemon = True
        self.output_thread.start()
    
    def _output_worker(self):
        """出力ワーカースレッド"""
        while self.running:
            try:
                # キューからデータを取得（ブロッキング）
                data = self.data_queue.get(timeout=1.0)
                
                # 各出力ハンドラにデータを送信
                for handler in self.output_handlers:
                    try:
                        handler.output(data)
                    except Exception as e:
                        logger.error(f"データ出力エラー: {e}")
                
                self.data_queue.task_done()
                
            except Exception as e:
                if self.running and not isinstance(e, Queue.Empty):  # 終了中でなく、タイムアウト以外のエラー
                    logger.error(f"出力スレッドエラー: {e}")
    
    def stop_output_thread(self):
        """出力スレッドを停止"""
        self.running = False
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(2.0)  # 最大2秒待機