#!/usr/bin/env python3
# hems_data_collector.py（プロジェクトルート）

import sys
import os
import logging

logger = logging.getLogger(__name__)

# srcディレクトリへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# メイン関数をインポートして実行
from src.main import main

if __name__ == "__main__":
    logger.info(" hems_data_collector を起動します")
    main()