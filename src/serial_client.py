# src/serial_client.py
import serial
import time
import re
import logging
import traceback
from queue import Queue, Empty
import threading

from src.config import (
    SERIAL_PORT, SERIAL_RATE, B_ROUTE_ID, B_ROUTE_PASSWORD, 
    ECHONET_PROPERTY_CODES
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
        self.ipv6_addr = None
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
        version_response = self.send_command("SKVER")
        bp35a1_version = "Unknown"
        if version_response:
            for line in version_response.splitlines():
                if line.startswith("EVER"):
                    bp35a1_version = line
                    break
        logger.info(f"BP35A1バージョン: {bp35a1_version.strip()}")
        
        # Bルート認証情報の設定
        logger.info("Bルート認証情報を設定...")
        self.send_command(f"SKSETRBID {B_ROUTE_ID}")
        self.send_command(f"SKSETPWD C {B_ROUTE_PASSWORD}")
        
        # ネットワークスキャンの実行
        logger.info(f"ネットワークスキャンを実行中...")
        response = self.send_command(f"SKSCAN 2 FFFFFFFF 6", wait_time=10)
        
        # スキャン結果からPANアドレスを取得
        pan_addr_match = re.search(r'Addr:([0-9A-F]{16})', response)
        if not pan_addr_match:
            logger.error("PANデスクリプタが見つかりませんでした")
            return False
            
        pan_addr = pan_addr_match.group(1)
        logger.info(f"見つかったPANアドレス: {pan_addr}")

        # PANアドレスをIPV6アドレスに変換
        logger.info(f"PANアドレス: {pan_addr} をIPV6アドレスに変換...")
        ipv6_addr_response = self.send_command(f"SKLL64 {pan_addr}")
        ipv6_addr_match = re.search(r'([0-9A-Fa-f]{1,4}(:[0-9A-Fa-f]{1,4}){7})', ipv6_addr_response)
        if not ipv6_addr_match:
            logger.error("IPV6アドレスが見つかりませんでした")
            return False
        self.ipv6_addr = ipv6_addr_match.group(1)
        logger.info(f"IPV6アドレス: {self.ipv6_addr}")
        
        # チャンネルを設定
        channel_match = re.search(r'Channel:([0-9A-F]{2})', response)
        if channel_match:
            channel = channel_match.group(1)
            logger.info(f"チャンネルを {channel} に設定...")
            self.send_command(f"SKSREG S2 {channel}")
        
        # PANIDを設定
        pan_id_match = re.search(r'Pan ID:([0-9A-F]{4})', response)
        if pan_id_match:
            pan_id = pan_id_match.group(1)
            logger.info(f"PANIDを {pan_id} に設定...")
            self.send_command(f"SKSREG S3 {pan_id}")
        
        # PANAに接続
        logger.info("PANAに接続中...")
        # SKJOINコマンドの応答 "OK" を期待する。 wait_timeは短く、send_command内部のtimeoutでOKを待つ。
        join_response = self.send_command(f"SKJOIN {self.ipv6_addr}", expected_response="OK", wait_time=0.1)

        if not join_response or "OK" not in join_response:
            logger.error(f"PANA接続コマンド(SKJOIN {self.ipv6_addr})の送信に失敗、またはOK応答がありませんでした。応答: {join_response}")
            return False

        # 接続完了(EVENT 25)を待機
        logger.info("PANA接続完了(EVENT 25)を待機中...")
        event_25_received = False
        for i in range(30):  # 最大30秒待機 (PANA接続には時間がかかる場合がある)
            if not self.running: # 途中で停止された場合
                 logger.info("初期化処理が中断されました。(イベント待機中)")
                 return False
            
            # シリアルポートから1行読み取りを試みる (ノンブロッキングに近い形で)
            line = ""
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        logger.debug(f"受信 (イベント待機中 Loop {i+1}/30): {line}")
                except Exception as e:
                    logger.warning(f"イベント待機中のシリアル読み取りエラー: {e}")
                    # ポートが閉じられたなどの可能性もあるので、少し待ってリトライ
                    time.sleep(0.1)
                    continue
            
            if line.startswith("EVENT 24"): # PANA接続失敗
                logger.error("PANA接続に失敗しました (EVENT 24)")
                return False
            elif line.startswith("EVENT 25"):  # 接続成功イベント
                logger.info("スマートメーターに接続しました (EVENT 25)")
                self.connected = True
                event_25_received = True
                return True # initialize成功
            
            time.sleep(1) # 1秒待機

        if not event_25_received:
            logger.error("PANA接続タイムアウト (EVENT 25が30秒以内に受信できませんでした)")
            # SKTERMを送信してPANAセッションを終了させることを検討
            # logger.info("SKTERMを送信してPANAセッションを終了します。")
            # self.send_command("SKTERM", wait_time=1, expected_response="OK")
            return False
        
        logger.error("スマートメーターへの接続に失敗しました (予期せぬフロー)")
        return False
    
    def get_property(self, property_code, transaction_id=1):
        """指定したプロパティ値を取得"""
        if not self.connected:
            logger.error("スマートメーターに接続されていません")
            return None
            
        # ECHONET Lite要求の作成
        # データ長は64バイト（実際の長さに応じて調整）
        command = f"SKSENDTO 1 {self.ipv6_addr} 0E1A 1 0040 "
        
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
                if self.running and not isinstance(e, Empty):  # 終了中でなく、タイムアウト以外のエラー
                    logger.error(f"出力スレッドエラー: {e}")
    
    def stop_output_thread(self):
        """出力スレッドを停止"""
        self.running = False
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(2.0)  # 最大2秒待機