# src/config.py
"""アプリケーション全体で使用する設定値。

このモジュールは、シリアル通信、Bルート認証情報、データ出力先、
ECHONET Lite関連の定数など、アプリケーション全体で共有される設定値を定義します。

環境変数から設定を読み込み、環境変数が存在しない場合は
定義済みのデフォルト値を使用します。
"""
import os
import logging
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# アプリケーションのバージョン
VERSION = "0.1.0"

# シリアル通信設定
SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')  # USBトングルのシリアルポート（環境に合わせて変更）
SERIAL_RATE = int(os.environ.get('SERIAL_RATE', 115200))          # ボーレート

# Bルート認証情報（電力会社から提供される）
B_ROUTE_ID = os.environ.get('B_ROUTE_ID', "00000000000000000000000000000000")  # 認証ID
B_ROUTE_PASSWORD = os.environ.get('B_ROUTE_PASSWORD', "00000000000000000000000000000000")  # パスワード

# データファイル
DEFAULT_DATA_FILE = "hems_data.dat"

# Google Cloud Pub/Sub設定
GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID', "your-project-id")  # Google Cloudプロジェクト
GCP_TOPIC_NAME = os.getenv('GCP_TOPIC_NAME', 'hems-data')

# デフォルトの実行スケジュール（5分ごと）
DEFAULT_SCHEDULE = '*/5 * * * *' 
# デフォルトの実行間隔（秒）
DEFAULT_INTERVAL = 300
# デフォルトのWebhook URL
DEFAULT_WEBHOOK_URL = "http://localhost:8000/webhook"

# ECHONET Lite関連の定数
ECHONET_PROPERTY_CODES = {
    'CUMULATIVE_POWER': "E0",  # 積算電力量計測値
    'CUMULATIVE_POWER_UNIT': "E1", # 積算電力量単位
    'HISTORICAL_CUMULATIVE_POWER': "EA", # 定時積算電力量計測値
    'INSTANT_POWER': "E7",     # 瞬時電力計測値
    'CURRENT_VALUE': "E8",     # 瞬時電流計測値
}

# CSV出力用ヘッダー
CSV_HEADERS = [
    'timestamp', 
    'cumulative_power_kwh', 
    'instant_power_w', 
    'current_r_a', 
    'current_t_a',
    'historical_timestamp',
    'historical_cumulative_power_kwh'
]