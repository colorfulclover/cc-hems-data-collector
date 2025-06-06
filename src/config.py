# src/config.py
"""アプリケーション全体で使用する設定値。

このモジュールは、シリアル通信、Bルート認証情報、データ出力先、
ECHONET Lite関連の定数など、アプリケーション全体で共有される設定値を定義します。

環境変数から設定を読み込み、環境変数が存在しない場合は
定義済みのデフォルト値を使用します。
"""
import os
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# シリアル通信設定
SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')  # USBトングルのシリアルポート（環境に合わせて変更）
SERIAL_RATE = int(os.environ.get('SERIAL_RATE', 115200))          # ボーレート

# Bルート認証情報（電力会社から提供される）
B_ROUTE_ID = os.environ.get('B_ROUTE_ID', "00000000000000000000000000000000")  # 認証ID
B_ROUTE_PASSWORD = os.environ.get('B_ROUTE_PASSWORD', "00000000000000000000000000000000")  # パスワード

# データファイル
DEFAULT_DATA_FILE = "hems_data.dat"

# Google Cloud Pub/Sub設定
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', "your-project-id")  # Google Cloudプロジェクト
TOPIC_NAME = os.environ.get('GCP_TOPIC_NAME', "hems-data")  # Pub/Subトピック名

# データ取得間隔（秒）
DEFAULT_INTERVAL = 300

# ECHONET Lite関連の定数
ECHONET_PROPERTY_CODES = {
    'CUMULATIVE_POWER': "E0",  # 積算電力量計測値
    'INSTANT_POWER': "E7",     # 瞬時電力計測値
    'CURRENT_VALUE': "E8",     # 瞬時電流計測値
}

# CSV出力用ヘッダー
CSV_HEADERS = ['timestamp', 'cumulative_power_kwh', 'instant_power_w', 'current_r_a', 'current_t_a']