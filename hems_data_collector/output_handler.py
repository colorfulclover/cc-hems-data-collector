# src/output_handler.py
"""取得した電力データの出力処理を担当するモジュール。

さまざまな形式（標準出力、ファイル、Google Cloud Pub/Sub, Webhook）で
電力消費量データを出力するためのハンドラを提供します。
"""
import os
import logging
import json
import yaml
import requests
from datetime import datetime

from hems_data_collector.config import CSV_HEADERS

logger = logging.getLogger(__name__)

class OutputHandler:
    """データ出力処理を行うクラス。
    
    Attributes:
        output_type (str): 出力タイプ ('stdout', 'file', 'gcloud', 'webhook')。
        output_format (str): 出力フォーマット ('json', 'yaml', 'csv')。
        filepath (str): ファイル出力時のパス。
        project_id (str): Google CloudプロジェクトID。
        topic_name (str): Pub/Subトピック名。
        publisher (pubsub_v1.PublisherClient): Pub/Subクライアント。
        topic_path (str): Pub/Subトピックのフルパス。
        webhook_url (str): Webhookの送信先URL。
    """
    
    def __init__(self, output_type, output_format='json', filepath=None, 
                 project_id=None, topic_name=None, webhook_url=None):
        """OutputHandlerを初期化します。

        Args:
            output_type (str): 出力タイプ ('stdout', 'file', 'gcloud', 'webhook')。
            output_format (str, optional): 出力フォーマット ('json', 'yaml', 'csv')。
                'gcloud' または 'webhook' タイプの場合は 'json' に固定されます。
                Defaults to 'json'.
            filepath (str, optional): ファイル出力先のパス。
                'file' タイプの場合に必要です。Defaults to None.
            project_id (str, optional): Google CloudプロジェクトID。
                'gcloud' タイプの場合に必要です。Defaults to None.
            topic_name (str, optional): Pub/Subトピック名。
                'gcloud' タイプの場合に必要です。Defaults to None.
            webhook_url (str, optional): Webhookの送信先URL。
                'webhook' タイプの場合に必要です。Defaults to None.
        """
        self.type = output_type
        self.format = output_format
        self.filepath = filepath
        self.project_id = project_id
        self.topic_name = topic_name
        self.webhook_url = webhook_url
        self.publisher = None
        self.topic_path = None
        self.headers = {'Content-Type': 'application/json'}
        
        # Google Cloud Pub/Sub クライアントの初期化
        if self.type == 'gcloud':
            try:
                from google.cloud import pubsub_v1
                self.publisher = pubsub_v1.PublisherClient()
                self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
            except ImportError:
                self.publisher = None
                self.topic_path = None
                logger.error("google-cloud-pubsubがインストールされていません。")
            except Exception as e:
                self.publisher = None
                self.topic_path = None
                logger.error(f"Pub/Subクライアントの初期化に失敗しました: {e}")

    def output(self, data):
        """データを指定された形式と場所に出力します。

        Args:
            data (dict): 出力する電力データ。
        """
        try:
            data_str = self._get_formatted_string(data)
            if not data_str:
                return

            if self.type == 'stdout':
                print(data_str)
            elif self.type == 'file':
                self._output_to_file(data_str)
            elif self.type == 'gcloud':
                self._output_to_gcloud(data_str)
            elif self.type == 'webhook':
                self._output_to_webhook(data_str)
        except Exception as e:
            logger.error(f"{self.type}への出力中にエラーが発生しました: {e}")

    def _get_formatted_string(self, data):
        """データを指定されたフォーマットの文字列に変換します。"""
        if self.format == 'json':
            return json.dumps(data)
        elif self.format == 'yaml':
            return yaml.dump(data, default_flow_style=False)
        elif self.format == 'csv':
            # ヘッダーが存在しない場合やファイルが空の場合にヘッダーを書き込む
            if self.filepath and (not os.path.exists(self.filepath) or os.path.getsize(self.filepath) == 0):
                self._output_to_file(','.join(CSV_HEADERS), append=False)
            
            row_data = [
                str(data.get('timestamp', '')),
                str(data.get('cumulative_power_kwh', '')),
                str(data.get('instant_power_w', '')),
                str(data.get('current_a', '')),
                str(data.get('current_r_a', '')),
                str(data.get('current_t_a', '')),
                str(data.get('historical_timestamp', '')),
                str(data.get('historical_cumulative_power_kwh', '')),
                str(data.get('recent_30min_timestamp', '')),
                str(data.get('recent_30min_consumption_kwh', ''))
            ]
            return ','.join(row_data)
        return None

    def _output_to_file(self, data_str, append=True):
        """ファイルに文字列を書き込みます。"""
        mode = 'a' if append else 'w'
        try:
            with open(self.filepath, mode, encoding='utf-8') as f:
                f.write(data_str + '\n')
            logger.info(f"ファイルにデータを書き込みました: {self.filepath}")
        except IOError as e:
            logger.error(f"ファイル書き込みエラー ({self.filepath}): {e}")

    def _output_to_gcloud(self, data_str):
        """データをGoogle Cloud Pub/Subに送信します。"""
        if not self.publisher or not self.topic_path:
            logger.error("Pub/Subクライアントが初期化されていません。")
            return
        
        future = self.publisher.publish(self.topic_path, data_str.encode('utf-8'))
        future.result()  # 送信完了を待機
        logger.info(f"Google Cloud Pub/Subトピックにメッセージを送信しました: {self.topic_path}")
    
    def _output_to_webhook(self, data_str):
        """データをJSONとしてWebhookにPOST送信します。

        Args:
            data_str (str): 送信するJSON文字列。
        """
        if not self.webhook_url:
            logger.error("Webhook URLが設定されていません。")
            return
        
        try:
            response = requests.post(self.webhook_url, data=data_str, headers=self.headers, timeout=10)
            response.raise_for_status()  # 2xx以外のステータスコードで例外を発生
            logger.info(f"Webhookにデータを送信しました: {self.webhook_url} (ステータス: {response.status_code})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhookへの送信に失敗しました: {e}")