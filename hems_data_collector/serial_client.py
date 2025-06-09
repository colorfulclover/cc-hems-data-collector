# src/serial_client.py
"""スマートメーターとのシリアル通信を処理するクライアント。

Wi-SUNモジュール(BP35A1)を介してスマートメーターと通信し、
PANAセッションの確立、ECHONET Liteコマンドの送受信、
および電力データの取得を行います。
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
    """スマートメーターとの通信を管理するメインクラス。

    シリアルポートの開閉、Wi-SUNモジュールの初期化、PANAセッションの管理、
    ECHONET Liteプロパティの要求、およびデータ出力スレッドの制御を行います。

    Attributes:
        port (str): シリアルポート名 (例: '/dev/ttyUSB0')。
        baudrate (int): ボーレート (例: 115200)。
        ser (serial.Serial): `pyserial` のシリアルポートインスタンス。
        connected (bool): PANAセッションが確立されているかを示すフラグ。
        ipv6_addr (str): 接続したスマートメーターのIPv6アドレス。
        output_handlers (list): データ出力ハンドラのリスト。
        data_queue (Queue): 出力データを保持するキュー。
        output_thread (threading.Thread): 出力処理を行うワーカースレッド。
        running (bool): スレッドの実行状態を制御するフラグ。
    """
    def __init__(self, port=SERIAL_PORT, baudrate=SERIAL_RATE, output_handlers=None,
                 meter_channel=None, meter_pan_id=None, meter_ipv6_addr=None):
        """SmartMeterClientを初期化します。

        Args:
            port (str, optional): 使用するシリアルポート。
                Defaults to SERIAL_PORT.
            baudrate (int, optional): 通信ボーレート。
                Defaults to SERIAL_RATE.
            output_handlers (list, optional): データ出力ハンドラのリスト。
                Defaults to None.
            meter_channel (str, optional): スマートメーターのチャンネル。指定しない場合はスキャン。
            meter_pan_id (str, optional): スマートメーターのPAN ID。指定しない場合はスキャン。
            meter_ipv6_addr (str, optional): スマートメーターのIPv6アドレス。指定しない場合はスキャン。
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
        """シリアルポートを開きます。

        Returns:
            bool: ポートのオープンに成功した場合はTrue、失敗した場合はFalse。
        """
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
        """シリアルポートを閉じます。"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("シリアルポートを閉じました")
    
    def send_command(self, command, command_parts=None, wait_time=1, expected_response=None, timeout=10, add_newline=True):
        """コマンドを送信し、応答を待機します。

        この関数は、テキストコマンドと、それに続く追加のバイナリデータを
        送信することができます。

        Args:
            command (str): 送信するテキストコマンド部分。
            command_parts (bytes, optional): コマンドに続いて送信する
                追加のバイナリデータ。Defaults to None.
            wait_time (int, optional): コマンド送信後に待機する秒数。
                Defaults to 1.
            expected_response (str, optional): 応答に含まれることを期待する文字列。
                これが見つかった場合、即座に応答を返します。Defaults to None.
            timeout (int, optional): 応答を待つ最大秒数。Defaults to 10.
            add_newline (bool, optional): テキストコマンドの末尾に改行コード
                `\\r\\n` を付与するかどうか。Defaults to True.

        Returns:
            str | None: 受信した応答文字列。タイムアウトした場合はNone。
        """
        if not self.ser or not self.ser.is_open:
            logger.error("シリアルポートが開いていません")
            return None
        
        # コマンドの末尾に改行を追加（必要な場合）
        if add_newline and not command.endswith('\r\n'):
            command += '\r\n'
        
        # コマンド送信
        if  command_parts is None:
            logger.debug(f"送信: {command.strip()}")
            self.ser.write(command.encode('utf-8'))
        else:
            logger.debug(f"送信: {command.strip()} {command_parts}")
            self.ser.write(command.encode('utf-8') + command_parts)
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
        """Wi-SUNモジュールを初期化し、スマートメーターへ接続します。

        Bルート認証、PANスキャン、PANAセッション確立までの一連の
        シーケンスを実行します。

        Returns:
            bool: 初期化と接続に成功した場合はTrue、失敗した場合はFalse。
        """
        if not self.open_connection():
            return False
        
        # スキャンモードをアクティブに設定
        logger.info("初期化を開始...")
        
        # バージョン情報の取得
        version_response = self.send_command("SKVER")
        bp35a1_version = "Unknown"
        if version_response:
            for line in version_response.splitlines():
                if line.startswith("EVER"):
                    bp35a1_version = line
                    break
        logger.info(f"FW バージョン: {bp35a1_version.strip()}")
        
        # Bルート認証情報の設定
        logger.info("Bルート認証情報を設定...")
        self.send_command(f"SKSETRBID {B_ROUTE_ID}")
        self.send_command(f"SKSETPWD C {B_ROUTE_PASSWORD}")
        
        # チャンネル、PAN ID、IPv6アドレスが指定されているかチェック
        if self.meter_channel and self.meter_pan_id and self.ipv6_addr:
            logger.info("指定された情報を使用して接続を試みます...")
            logger.info(f"チャンネルを {self.meter_channel} に設定...")
            self.send_command(f"SKSREG S2 {self.meter_channel}")
            
            logger.info(f"PAN IDを {self.meter_pan_id} に設定...")
            self.send_command(f"SKSREG S3 {self.meter_pan_id}")
            
            # この場合、self.ipv6_addr は初期化時に設定済み
            logger.info(f"IPv6アドレス: {self.ipv6_addr}")

        else:
            logger.info("接続情報をスキャンで取得します...")
            # ネットワークスキャンの実行
            logger.info(f"ネットワークスキャンを実行中...")
            response = self.send_command(f"SKSCAN 2 FFFFFFFF 6", wait_time=20)
            
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
    
    def _wait_for_echonet_response(self, property_code, request_tid_hex, expected_esv='72'):
        """指定したTIDを持つECHONET Liteの応答を待ち受けます。"""
        logger.info(f"ERXUDP待機開始 (プロパティ: {property_code}, ESV: {expected_esv})")
        start_time = time.time()
        while time.time() - start_time < 20: # タイムアウトを20秒に設定
            if not self.running:
                logger.info("データ取得が中断されました。(ERXUDP 待機中)")
                return None
            
            line = ""
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: logger.debug(f"受信 (ERXUDP 待機中): {line}")
                except Exception as e:
                    logger.warning(f"ERXUDP 待機中のシリアル読み取りエラー: {e}")
            
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

                    # 期待するESV（Get_Res or Set_Res）か確認
                    if parsed_frame['ESV'].upper() == expected_esv.upper():
                        # プロパティコードが含まれているか確認
                        if any(prop['EPC'] == property_code.upper() for prop in parsed_frame['properties']):
                             logger.info(f"ERXUDP受信成功 (プロパティ: {property_code}): {echonet_data_hex}")
                             return echonet_data_hex
                    # ESVがSNA(50番台)などのエラー応答の場合
                    elif parsed_frame['ESV'].startswith('5'):
                        logger.warning(f"ECHONET Liteエラー応答(SNA)を受信しました: ESV={parsed_frame['ESV']}")
                        return None # エラー応答なのでNoneを返す
                    else:
                        logger.debug(f"期待する応答(ESV={expected_esv})ではありませんでした: ESV={parsed_frame['ESV']}")
                        # 他の応答は無視して待機を続ける
            elif "FAIL" in line:
                logger.error(f"ERXUDP待機中にFAILを受信しました: {line}")
                return None
        
        logger.warning(f"ERXUDP待機タイムアウト (プロパティ: {property_code})")
        return None

    def get_property(self, property_code, transaction_id=1):
        """指定したECHONET Liteプロパティの値を取得します。

        SKSENDTOコマンドでECHONET LiteのGet要求を送信し、ERXUDPで応答を待ち受けます。

        Args:
            property_code (str): 取得するプロパティのEPCコード（16進数文字列）。
            transaction_id (int, optional): ECHONET LiteのトランザクションID。
                Defaults to 1.

        Returns:
            str | None: 受信したECHONET Liteフレームのデータ部分（16進数文字列）。
                成功応答(ESV=72)の場合にフレームを返します。失敗した場合はNone。
        """
        if not self.connected:
            logger.error("PANAセッションが確立されていません。get_propertyをスキップします。")
            return None

        request_tid_hex = format(transaction_id, "04X")
        try:
            # ECHONET Lite電文をバイト列(bytes)として構築
            echonet_lite_frame_bytes = (
                b'\x10\x81'        # EHD
                + transaction_id.to_bytes(2, 'big')        # TID
                + b'\x05\xFF\x01'  # SEOJ (送信元)
                + b'\x02\x88\x01'  # DEOJ (宛先)
                + b'\x62'          # ESV (Get)
                + b'\x01'          # OPC (処理プロパティ数)
                + int(property_code, 16).to_bytes(1, 'big') # EPC (プロパティコード)
                + b'\x00'          # PDC (データカウンタ)
            )
        except Exception as e:
            logger.error(f"ECHONET Lite GETフレームの構築に失敗しました: {e}")
            return None

        # DATALENの計算
        data_len_bytes = len(echonet_lite_frame_bytes)
        datalen_hex_str = format(data_len_bytes, '04X')

        # SKSENDTOコマンドの組み立て
        base_sksendto_command = f"SKSENDTO 1 {self.ipv6_addr} 0E1A 1"
        full_sksendto_command = f"{base_sksendto_command} {datalen_hex_str} "

        # 2. SKSENDTOコマンドの実行と応答確認
        logger.debug(f"SKSENDTO送信: {full_sksendto_command}")
        sksendto_response = self.send_command(full_sksendto_command, command_parts=echonet_lite_frame_bytes, expected_response="OK", wait_time=0.2, add_newline=False) # wait_timeはOK/FAIL応答受信までの時間

        if not sksendto_response:
            logger.error(f"SKSENDTOコマンドへの応答がありませんでした: {sksendto_response.strip()}")
            return None
        
        if "FAIL" in sksendto_response:
            logger.error(f"SKSENDTOコマンドが失敗しました: {sksendto_response.strip()}")
            return None
        
        if "OK" not in sksendto_response:
            logger.error(f"SKSENDTO(GET)コマンドの送信に失敗、またはOK応答がありませんでした: {sksendto_response.strip()}")
            return None

        return self._wait_for_echonet_response(property_code, request_tid_hex, expected_esv='72')

    def set_property(self, property_code, edt, transaction_id=1):
        """指定したECHONET Liteプロパティの値を設定します (SetC)。

        SKSENDTOコマンドでECHONET LiteのSetC要求を送信し、ERXUDPで応答を待ち受けます。

        Args:
            property_code (str): 設定するプロパティのEPCコード（16進数文字列）。
            edt (str): 設定するデータ（EDT）の16進数文字列。
            transaction_id (int, optional): ECHONET LiteのトランザクションID。
                Defaults to 1.

        Returns:
            str | None: 受信したECHONET Liteフレームのデータ部分（16進数文字列）。
                成功応答(ESV=71)の場合にフレームを返します。失敗した場合はNone。
        """
        if not self.connected:
            logger.error("PANAセッションが確立されていません。set_propertyをスキップします。")
            return None

        request_tid_hex = format(transaction_id, "04X")
        try:
            # ECHONET Lite電文をバイト列(bytes)として構築
            edt_bytes = bytes.fromhex(edt)
            echonet_lite_frame_bytes = (
                b'\x10\x81'        # EHD
                + transaction_id.to_bytes(2, 'big')        # TID
                + b'\x05\xFF\x01'  # SEOJ (送信元)
                + b'\x02\x88\x01'  # DEOJ (宛先)
                + b'\x61'          # ESV (SetC)
                + b'\x01'          # OPC (処理プロパティ数)
                + int(property_code, 16).to_bytes(1, 'big') # EPC (プロパティコード)
                + len(edt_bytes).to_bytes(1, 'big')      # PDC (データカウンタ)
                + edt_bytes        # EDT (データ本体)
            )
        except Exception as e:
            logger.error(f"ECHONET Lite SETフレームの構築に失敗しました: {e}")
            return None

        datalen_hex_str = format(len(echonet_lite_frame_bytes), '04X')
        full_sksendto_command = f"SKSENDTO 1 {self.ipv6_addr} 0E1A 1 {datalen_hex_str} "

        sksendto_response = self.send_command(
            full_sksendto_command, command_parts=echonet_lite_frame_bytes,
            expected_response="OK", wait_time=0.2, add_newline=False
        )

        if not sksendto_response or "OK" not in sksendto_response:
            response_str = sksendto_response.strip() if sksendto_response else "None"
            logger.error(f"SKSENDTO(SET)コマンドの送信に失敗、またはOK応答がありませんでした: {response_str}")
            return None

        return self._wait_for_echonet_response(property_code, request_tid_hex, expected_esv='71')

    def get_meter_data(self):
        """スマートメーターから主要な電力データをまとめて取得します。"""
        if not self.connected:
            logger.error("スマートメーターに接続されていません")
            return None
        
        data = {}
        data['timestamp'] = get_current_timestamp()
        
        try:
            # 積算電力量の単位(E1)を先に取得
            logger.info("積算電力量の単位を要求中...")
            unit_response = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_UNIT'], 1)
            unit_hex_value = parse_echonet_response(unit_response, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_UNIT'])
            power_multiplier = parse_power_unit(unit_hex_value)

            # 積算電力量計測値の取得
            logger.info("積算電力量を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'], 2)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER'])
            if hex_value:
                power_value = parse_cumulative_power(hex_value, power_multiplier)
                if power_value is not None:
                    data['cumulative_power_kwh'] = power_value
                    logger.info(f"積算電力量: {power_value} kWh (単位乗数: {power_multiplier})")
            
            # 瞬時電力計測値の取得
            logger.info("瞬時電力を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['INSTANT_POWER'], 3)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['INSTANT_POWER'])
            if hex_value:
                power_value = parse_instant_power(hex_value)
                if power_value is not None:
                    data['instant_power_w'] = power_value
                    logger.info(f"瞬時電力: {power_value} W")
            
            # 瞬時電流計測値の取得
            logger.info("瞬時電流を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['CURRENT_VALUE'], 4)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['CURRENT_VALUE'])
            if hex_value:
                current_data = parse_current_value(hex_value)
                if current_data:
                    data.update(current_data)
                    # ログ出力のキー名を修正
                    if current_data.get('current_t_a') is None:
                        # 単相
                        logger.info(f"瞬時電流: {current_data.get('current_a')} A")
                    else:
                        # 三相
                        logger.info(f"瞬時電流: R相={current_data.get('current_r_a')} A, T相={current_data.get('current_t_a')} A (合計: {current_data.get('current_a')} A)")
            
            # 定時積算電力量計測値(EA)の取得
            logger.info("定時積算電力量を要求中...")
            response = self.get_property(ECHONET_PROPERTY_CODES['HISTORICAL_CUMULATIVE_POWER'], 5)
            hex_value = parse_echonet_response(response, ECHONET_PROPERTY_CODES['HISTORICAL_CUMULATIVE_POWER'])
            if hex_value:
                historical_data = parse_historical_power(hex_value, power_multiplier)
                if historical_data:
                    data.update(historical_data)
                    logger.info(f"定時積算電力量: {historical_data['historical_cumulative_power_kwh']} kWh ({historical_data['historical_timestamp']})")

            # 積算電力量計測値履歴1(E2)から30分消費電力を取得
            today_history_hex = None
            logger.info("積算履歴収集日(E5)を「本日」に設定中...")
            if self.set_property(ECHONET_PROPERTY_CODES['SET_CUMULATIVE_HISTORY_DAY'], '00', 6):
                logger.info("積算電力量履歴1(E2)の「本日」分を要求中...")
                today_history_frame = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'], 7)
                today_history_hex = parse_echonet_response(today_history_frame, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'])
            else:
                logger.warning("積算履歴収集日(E5)の「本日」設定に失敗しました。")

            # まず本日分のデータだけで計算を試みる
            consumption_data = parse_cumulative_power_history(today_history_hex, multiplier=power_multiplier)

            # 計算できなかった場合（日付またぎ等）、昨日分のデータを取得して再試行
            if not consumption_data and today_history_hex is not None:
                logger.info("30分消費電力の計算にデータが不足している可能性があるため、昨日分の履歴を取得します。")
                yesterday_history_hex = None
                logger.info("積算履歴収集日(E5)を「昨日」に設定中...")
                if self.set_property(ECHONET_PROPERTY_CODES['SET_CUMULATIVE_HISTORY_DAY'], '01', 8):
                    logger.info("積算電力量履歴1(E2)の「昨日」分を要求中...")
                    yesterday_history_frame = self.get_property(ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'], 9)
                    yesterday_history_hex = parse_echonet_response(yesterday_history_frame, ECHONET_PROPERTY_CODES['CUMULATIVE_POWER_HISTORY_1'])
                else:
                    logger.warning("積算履歴収集日(E5)の「昨日」設定に失敗しました。")

                # 本日分と昨日分を合わせて再計算
                consumption_data = parse_cumulative_power_history(
                    today_history_hex,
                    yesterday_edt=yesterday_history_hex,
                    multiplier=power_multiplier
                )

            if consumption_data:
                data.update(consumption_data)
                logger.info(f"直近30分消費電力量: {consumption_data['recent_30min_consumption_kwh']} kWh ({consumption_data['recent_30min_timestamp']})")
            else:
                logger.info("最終的に30分消費電力は計算できませんでした。")

            return data if len(data) > 1 else None  # タイムスタンプ以外のデータがある場合のみ返す
            
        except Exception as e:
            logger.error(f"データ取得中にエラーが発生しました: {e}")
            traceback.print_exc()
            return None

    def start_output_thread(self):
        """データ出力用のワーカースレッドを開始します。"""
        self.running = True
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.daemon = True
        self.output_thread.start()
    
    def _output_worker(self):
        """データキューからデータを取り出し、出力ハンドラに渡すワーカースレッド。"""
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
        """データ出力用のワーカースレッドを停止します。"""
        self.running = False
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(2.0)  # 最大2秒待機