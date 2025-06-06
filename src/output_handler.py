# src/output_handler.py
import os
import json
import csv
import yaml
import logging
from datetime import datetime

try:
    from google.cloud import pubsub_v1
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False

from src.config import CSV_HEADERS, PROJECT_ID, TOPIC_NAME

logger = logging.getLogger(__name__)

class OutputHandler:
    """取得した電力消費量データを様々な形式で出力するハンドラ。

    標準出力、ファイル（JSON, YAML, CSV）、Google Cloud Pub/Subへの
    データ出力機能を提供します。
    
    Attributes:
        output_type (str): 出力タイプ ('stdout', 'file', 'cloud')。
        output_format (str): 出力フォーマット ('json', 'yaml', 'csv')。
        file_path (str): ファイル出力時のパス。
        pubsub_project (str): Google CloudプロジェクトID。
        pubsub_topic (str): Pub/Subトピック名。
        pubsub_publisher (pubsub_v1.PublisherClient): Pub/Subクライアント。
        topic_path (str): Pub/Subトピックのフルパス。
    """
    
    def __init__(self, output_type, output_format=None, file_path=None, pubsub_project=None, pubsub_topic=None):
        """OutputHandlerを初期化します。

        Args:
            output_type (str): 出力タイプ ('stdout', 'file', 'cloud')。
            output_format (str, optional): 出力フォーマット ('json', 'yaml', 'csv')。
                Defaults to None.
            file_path (str, optional): ファイル出力時のパス。Defaults to None.
            pubsub_project (str, optional): Google CloudプロジェクトID。Defaults to None.
            pubsub_topic (str, optional): Pub/Subトピック名。Defaults to None.
        """
        self.output_type = output_type
        self.output_format = output_format
        self.file_path = file_path
        self.pubsub_project = pubsub_project or PROJECT_ID
        self.pubsub_topic = pubsub_topic or TOPIC_NAME
        self.pubsub_publisher = None
        
        # Google Cloud Pub/Sub初期化（必要な場合）
        if output_type == 'cloud' and PUBSUB_AVAILABLE:
            try:
                self.pubsub_publisher = pubsub_v1.PublisherClient()
                self.topic_path = self.pubsub_publisher.topic_path(self.pubsub_project, self.pubsub_topic)
                logger.info(f"Google Cloud Pub/Sub接続初期化: {self.topic_path}")
            except Exception as e:
                logger.error(f"Google Cloud Pub/Sub初期化エラー: {e}")
                self.pubsub_publisher = None
        
        # ファイル出力の初期化（必要な場合）
        if output_type == 'file' and file_path:
            if output_format == 'csv':
                # CSVファイルのヘッダーを書き込む
                if not os.path.exists(file_path):
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(CSV_HEADERS)
                        logger.info(f"CSVファイル初期化: {file_path}")
            
    def format_data(self, data):
        """データを指定されたフォーマットの文字列またはリストに変換します。

        Args:
            data (dict): フォーマットするデータ。

        Returns:
            str | list | None: 指定されたフォーマットの文字列（JSON, YAML）、
                またはリスト（CSV）。データがない場合はNone。
        """
        if not data:
            return None
            
        # タイムスタンプを追加（まだなければ）
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        if self.output_format == 'json':
            return json.dumps(data)
        elif self.output_format == 'yaml':
            return yaml.dump(data)
        elif self.output_format == 'csv':
            # CSVの1行を生成
            row = [
                data['timestamp'],
                data.get('cumulative_power', ''),
                data.get('instant_power', ''),
                data.get('current_r', data.get('current', '')),
                data.get('current_t', '')
            ]
            return row
        else:
            return str(data)
    
    def output(self, data):
        """データを設定された出力先に書き込みます。

        Args:
            data (dict): 出力するデータ。

        Returns:
            bool: 出力が成功した場合はTrue、失敗した場合はFalse。
        """
        if not data:
            logger.warning("出力するデータがありません")
            return False
        
        try:
            # データをフォーマット
            formatted_data = self.format_data(data)
            if not formatted_data:
                return False
            
            # 標準出力
            if self.output_type == 'stdout':
                if self.output_format == 'csv':
                    print(','.join(map(str, formatted_data)))
                else:
                    print(formatted_data)
            
            # ファイル出力
            elif self.output_type == 'file' and self.file_path:
                if self.output_format == 'json':
                    with open(self.file_path, 'a') as f:
                        f.write(formatted_data + '\n')
                elif self.output_format == 'yaml':
                    with open(self.file_path, 'a') as f:
                        f.write(formatted_data + '\n---\n')
                elif self.output_format == 'csv':
                    with open(self.file_path, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(formatted_data)
            
            # Google Cloud Pub/Sub
            elif self.output_type == 'cloud' and self.pubsub_publisher:
                if self.output_format == 'json':
                    data_bytes = formatted_data.encode('utf-8')
                    future = self.pubsub_publisher.publish(self.topic_path, data=data_bytes)
                    future.result()  # 結果を待機
                    logger.info(f"Pub/Subにデータを送信しました: {self.topic_path}")
                else:
                    logger.error(f"Pub/Subでは{self.output_format}フォーマットはサポートされていません。JSONを使用してください。")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"データ出力エラー: {e}")
            return False