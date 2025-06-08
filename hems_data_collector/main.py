# src/main.py
"""HEMSデータ収集アプリケーションのメインモジュール。

コマンドライン引数を解釈し、ロギングを設定し、
SmartMeterClientを初期化してデータ取得プロセスを開始します。
"""
import time
import logging
import argparse
import traceback
from datetime import datetime, timezone
from croniter import croniter

from hems_data_collector.config import (
    VERSION,
    DEFAULT_DATA_FILE, GCP_PROJECT_ID, GCP_TOPIC_NAME,
    SERIAL_PORT, SERIAL_RATE, DEFAULT_SCHEDULE, DEFAULT_INTERVAL,
    DEFAULT_WEBHOOK_URL
)
from hems_data_collector.serial_client import SmartMeterClient
from hems_data_collector.output_handler import OutputHandler
from hems_data_collector.logger_config import setup_logger

logger = logging.getLogger(__name__)


def parse_args():
    """コマンドライン引数を解析します。

    Returns:
        argparse.Namespace: パースされたコマンドライン引数を格納したオブジェクト。
    """
    parser = argparse.ArgumentParser(description='HEMSデータ取得ツール')
    
    # 出力タイプ
    parser.add_argument(
        '--output', '-o', choices=['stdout', 'file', 'gcloud', 'webhook'], 
        nargs='*', default=None, 
        help='出力タイプを1つ以上選択 (例: --output stdout file)。(デフォルト: なし、ログ出力のみ)'
    )
    
    # 出力フォーマット
    parser.add_argument('--format', '-f', choices=['json', 'yaml', 'csv'], 
                        default='json', help='出力フォーマット (デフォルト: json)')
    
    # ファイル出力パス
    parser.add_argument('--file', default=DEFAULT_DATA_FILE, 
                        help=f'ファイル出力パス (デフォルト: {DEFAULT_DATA_FILE})')
    
    # Google Cloud Pub/Sub設定
    parser.add_argument('--gcp-project', default=GCP_PROJECT_ID, 
                        help=f'Google CloudプロジェクトID (デフォルト: {GCP_PROJECT_ID})')
    parser.add_argument('--gcp-topic', default=GCP_TOPIC_NAME, 
                        help=f'Pub/Subトピック名 (デフォルト: {GCP_TOPIC_NAME})')
    
    # Webhook設定
    parser.add_argument('--webhook-url', default=DEFAULT_WEBHOOK_URL,
                        help=f'Webhook送信先URL (デフォルト: {DEFAULT_WEBHOOK_URL})')
    
    # シリアルポート設定
    parser.add_argument('--port', default=SERIAL_PORT, 
                        help=f'シリアルポート (デフォルト: {SERIAL_PORT})')
    parser.add_argument('--baudrate', type=int, default=SERIAL_RATE, 
                        help=f'ボーレート (デフォルト: {SERIAL_RATE})')

    # スマートメーター情報
    parser.add_argument('--meter-channel', type=str, help='スマートメーターのチャンネル')
    parser.add_argument('--meter-panid', type=str, help='スマートメーターのPAN ID')
    parser.add_argument('--meter-ipv6', type=str, help='スマートメーターのIPv6アドレス')
    
    # 実行モード設定
    parser.add_argument(
        '--mode', type=str, default='schedule', choices=['schedule', 'interval'],
        help='実行モード (デフォルト: schedule)'
    )
    # スケジュール設定
    parser.add_argument(
        '--schedule', '-s', type=str, default=DEFAULT_SCHEDULE,
        help=f'データ取得スケジュール（crontab形式, scheduleモードで有効, デフォルト: "{DEFAULT_SCHEDULE}")'
    )
    # 間隔設定
    parser.add_argument(
        '--interval', '-i', type=int, default=DEFAULT_INTERVAL,
        help=f'データ取得間隔（秒, intervalモードで有効, デフォルト: {DEFAULT_INTERVAL})'
    )
    
    # ログレベル設定
    parser.add_argument('--debug', action='store_true',
                        help='デバッグモードを有効化（詳細なログを出力）')
    
    # バージョン情報
    parser.add_argument('--version', '-v', action='version', version=f'%(prog)s {VERSION}',
                        help='バージョン情報を表示して終了します')

    return parser.parse_args()


def setup_output_handlers(args):
    """コマンドライン引数に基づいて出力ハンドラのリストをセットアップします。

    Args:
        args (argparse.Namespace): パースされたコマンドライン引数。

    Returns:
        list[OutputHandler]: セットアップされたOutputHandlerのインスタンスのリスト。
    """
    output_handlers = []
    
    if not args.output:
        return output_handlers

    if 'stdout' in args.output:
        output_handlers.append(OutputHandler('stdout', args.format))
    
    if 'file' in args.output:
        file_ext = {'json': '.json', 'yaml': '.yaml', 'csv': '.csv'}
        file_path = args.file
        if not any(file_path.endswith(ext) for ext in file_ext.values()):
            file_path += file_ext.get(args.format, '')
        
        output_handlers.append(OutputHandler('file', args.format, filepath=file_path))
    
    if 'gcloud' in args.output:
        try:
            from google.cloud import pubsub_v1
            output_handlers.append(OutputHandler('gcloud', 'json', project_id=args.gcp_project, topic_name=args.gcp_topic))
        except ImportError:
            logger.error("Google Cloud Pub/Sub機能が利用できません。パッケージをインストールしてください: pip install google-cloud-pubsub")

    if 'webhook' in args.output:
        output_handlers.append(OutputHandler('webhook', 'json', webhook_url=args.webhook_url))
    
    return output_handlers


def main():
    """アプリケーションのメイン実行関数。
    
    引数解析、ロギング設定、出力ハンドラとクライアントの初期化を行い、
    データ取得のメインループを開始します。
    """
    args = parse_args()
    
    # ロギングを設定
    setup_logger(args.debug)
    logger.info("hems_data_collector を起動します")
    
    if args.debug:
        logger.info("デバッグモードが有効になりました")
    
    # 出力ハンドラの作成
    output_handlers = setup_output_handlers(args)
    
    client = SmartMeterClient(
        port=args.port,
        baudrate=args.baudrate,
        output_handlers=output_handlers,
        meter_channel=args.meter_channel,
        meter_pan_id=args.meter_panid,
        meter_ipv6_addr=args.meter_ipv6
    )
    
    try:
        # 出力スレッドを開始
        client.start_output_thread()
        
        # 初期化とスマートメーターへの接続
        if not client.initialize():
            logger.error("初期化に失敗しました。プログラムを終了します。")
            return
        
        # 定期的にデータを取得
        if args.mode == 'schedule':
            # スケジュールモード
            base_time = datetime.now(timezone.utc)
            try:
                cron = croniter(args.schedule, base_time)
                logger.info(f"スケジュールモードで実行します。スケジュール: '{args.schedule}'")
            except ValueError as e:
                logger.error(f"不正なcron形式のスケジュールです: {args.schedule} - {e}")
                return

            while client.running:
                # 次の実行時刻まで待機
                next_run_datetime = cron.get_next(datetime)
                wait_seconds = (next_run_datetime - datetime.now(timezone.utc)).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"次の実行は {next_run_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')} です。({wait_seconds:.1f}秒後)")
                    sleep_end = time.time() + wait_seconds
                    while time.time() < sleep_end:
                        if not client.running:
                            # スリープ中に停止した場合、ループを抜ける
                            break
                        time.sleep(min(1, sleep_end - time.time()))
                
                if not client.running:
                    logger.info("クライアントが停止しました。")
                    break

                # データ取得
                try:
                    meter_data = client.get_meter_data()
                    if meter_data:
                        client.data_queue.put(meter_data)
                        logger.info(f"データを取得しました: {meter_data}")
                    else:
                        logger.info("データが取得できませんでした。")
                except Exception as e:
                    logger.error(f"データ取得中にエラーが発生しました: {e}")

        elif args.mode == 'interval':
            # インターバルモード
            logger.info(f"インターバルモードで実行します。間隔: {args.interval}秒")
            while client.running:
                if not client.running:
                    logger.info("クライアントが停止しました。")
                    break

                # データ取得
                try:
                    meter_data = client.get_meter_data()
                    if meter_data:
                        # データキューに追加
                        client.data_queue.put(meter_data)
                        logger.info(f"データを取得しました: {meter_data}")
                    else:
                        logger.info("データが取得できませんでした。")
                
                except KeyboardInterrupt:
                        raise
                except Exception as e:
                    logger.error(f"データ取得中にエラーが発生しました: {e}")

                # 指定間隔待機
                logger.info(f"{args.interval}秒後に再度データを取得します...")
                sleep_end = time.time() + args.interval
                while time.time() < sleep_end:
                    if not client.running:
                        # スリープ中に停止した場合、ループを抜ける
                        break
                    time.sleep(min(1, sleep_end - time.time()))

    except KeyboardInterrupt:
        logger.info("プログラムを終了します...")
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        client.stop_output_thread()
        client.close_connection()
        logger.info("クリーンアップを完了し、プログラムを終了しました。")


if __name__ == "__main__":
    main()