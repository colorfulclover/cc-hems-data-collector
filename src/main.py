# src/main.py
"""HEMSデータ収集アプリケーションのメインモジュール。

コマンドライン引数の解析、ロギング設定、出力ハンドラのセットアップ、
そしてスマートメータークライアントの初期化とデータ取得ループの実行を
担当します。
"""
import time
import logging
import argparse
import traceback
import os
import sys

# srcディレクトリへのパスを追加（直接実行時のみ必要）
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import (
    DEFAULT_DATA_FILE, DEFAULT_INTERVAL, PROJECT_ID, TOPIC_NAME,
    SERIAL_PORT, SERIAL_RATE
)
from src.serial_client import SmartMeterClient
from src.output_handler import OutputHandler

logger = logging.getLogger(__name__)

def parse_args():
    """コマンドライン引数を解析します。

    Returns:
        argparse.Namespace: パースされたコマンドライン引数を格納したオブジェクト。
    """
    parser = argparse.ArgumentParser(description='HEMSデータ取得ツール')
    
    # 出力タイプ
    parser.add_argument('--output', '-o', choices=['stdout', 'file', 'cloud', 'all'], 
                        default=None, help='出力タイプ (デフォルト: なし、ログ出力のみ)')
    
    # 出力フォーマット
    parser.add_argument('--format', '-f', choices=['json', 'yaml', 'csv'], 
                        default='json', help='出力フォーマット (デフォルト: json)')
    
    # ファイル出力パス
    parser.add_argument('--file', default=DEFAULT_DATA_FILE, 
                        help=f'ファイル出力パス (デフォルト: {DEFAULT_DATA_FILE})')
    
    # Google Cloud Pub/Sub設定
    parser.add_argument('--project', default=PROJECT_ID, 
                        help=f'Google Cloudプロジェクト (デフォルト: {PROJECT_ID})')
    parser.add_argument('--topic', default=TOPIC_NAME, 
                        help=f'Pub/Subトピック名 (デフォルト: {TOPIC_NAME})')
    
    # シリアルポート設定
    parser.add_argument('--port', default=SERIAL_PORT, 
                        help=f'シリアルポート (デフォルト: {SERIAL_PORT})')
    parser.add_argument('--baudrate', type=int, default=SERIAL_RATE, 
                        help=f'ボーレート (デフォルト: {SERIAL_RATE})')
    
    # 間隔設定
    parser.add_argument('--interval', '-i', type=int, default=DEFAULT_INTERVAL, 
                        help=f'データ取得間隔（秒） (デフォルト: {DEFAULT_INTERVAL})')
    
    # ログレベル設定
    parser.add_argument('--debug', action='store_true',
                        help='デバッグモードを有効化（詳細なログを出力）')
    
    return parser.parse_args()


def setup_output_handlers(args):
    """コマンドライン引数に基づいて出力ハンドラのリストをセットアップします。

    Args:
        args (argparse.Namespace): パースされたコマンドライン引数。

    Returns:
        list[OutputHandler]: セットアップされたOutputHandlerのインスタンスのリスト。
    """
    output_handlers = []
    
    if args.output == 'stdout' or args.output == 'all':
        output_handlers.append(OutputHandler('stdout', args.format))
    
    if args.output == 'file' or args.output == 'all':
        # ファイル拡張子の設定
        file_ext = {'json': '.json', 'yaml': '.yaml', 'csv': '.csv'}
        file_path = args.file
        if not any(file_path.endswith(ext) for ext in file_ext.values()):
            file_path += file_ext.get(args.format, '')
        
        output_handlers.append(OutputHandler('file', args.format, file_path))
    
    if args.output == 'cloud' or args.output == 'all':
        try:
            from google.cloud import pubsub_v1
            output_handlers.append(OutputHandler('cloud', 'json', None, args.project, args.topic))
        except ImportError:
            logger.error("Google Cloud Pub/Sub機能が利用できません。パッケージをインストールしてください: pip install google-cloud-pubsub")
    
    return output_handlers


def main():
    """アプリケーションのメイン実行関数。

    引数解析、ロギング設定、出力ハンドラとクライアントの初期化を行い、
    データ取得のメインループを開始します。
    KeyboardInterruptによる正常終了や、予期せぬエラーのハンドリングも行います。
    """
    args = parse_args()
    
    # ログレベルの設定
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("デバッグモードが有効になりました")
    
    # 出力ハンドラの作成
    output_handlers = setup_output_handlers(args)
    
    # スマートメータークライアントの作成
    client = SmartMeterClient(args.port, args.baudrate, output_handlers)
    
    try:
        # 出力スレッドを開始
        client.start_output_thread()
        
        # 初期化とスマートメーターへの接続
        if client.initialize():
            logger.info("スマートメーターへの接続に成功しました")
            
            # 定期的にデータを取得
            while True:
                try:
                    # データ取得
                    meter_data = client.get_meter_data()
                    
                    if meter_data:
                        # データキューに追加
                        client.data_queue.put(meter_data)
                        logger.info(f"データを取得しました: {meter_data}")
                    else:
                        logger.warning("データが取得できませんでした")
                    
                    # 指定間隔待機
                    logger.info(f"{args.interval}秒後に再度データを取得します...")
                    time.sleep(args.interval)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"データ取得中にエラーが発生しました: {e}")
                    time.sleep(60)  # エラー時は1分待機
        else:
            logger.error("スマートメーターへの接続に失敗しました")
    
    except KeyboardInterrupt:
        logger.info("プログラムを終了します")
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}")
        traceback.print_exc()
    finally:
        client.stop_output_thread()
        client.close_connection()
        logger.info("プログラムを終了しました")


if __name__ == "__main__":
    main()