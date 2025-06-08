"""アプリケーションのロギング設定を管理するモジュール。

このモジュールは、アプリケーション全体で使用されるロガーのセットアップを担当します。
タイムスタンプをUTCでフォーマットするカスタムフォーマッタと、
ロガーを初期化するための設定関数を提供します。
"""
import logging
from datetime import datetime, timezone

class UTCFormatter(logging.Formatter):
    """ログのタイムスタンプをUTCのISO 8601形式でフォーマットするクラス。

    logging.Formatterを継承し、formatTimeメソッドをオーバーライドすることで、
    ログのタイムスタンプを常にUTCで表示します。
    """
    def formatTime(self, record, datefmt=None):
        """ログレコードの作成時刻をUTCのISO形式文字列に変換します。

        Args:
            record (logging.LogRecord): ログレコードオブジェクト。
            datefmt (str, optional): 日付フォーマット文字列。
                このフォーマッタでは無視されます。Defaults to None.

        Returns:
            str: UTC基準のISO 8601形式のタイムスタンプ文字列。
        """
        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

def setup_logger(debug=False):
    """アプリケーションのルートロガーをセットアップします。

    コンソール出力用のStreamHandlerを設定し、タイムスタンプがUTCになるように
    UTCFormatterを適用します。既存のハンドラはすべて削除され、
    新しいハンドラに置き換えられます。

    Args:
        debug (bool, optional): Trueの場合、ログレベルをDEBUGに設定します。
            Falseの場合はINFOレベルになります。Defaults to False.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # ルートロガーを取得
    root_logger = logging.getLogger()
    
    # 既存のハンドラを全て削除（重複設定や意図しない出力を防ぐ）
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
            
    # 新しいコンソールハンドラとUTCフォーマッタを設定
    handler = logging.StreamHandler()
    formatter = UTCFormatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # ライブラリのログレベルを調整（必要に応じて）
    # logging.getLogger("urllib3").setLevel(logging.WARNING) 