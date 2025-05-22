#!/usr/bin/env python3
# hems_data_collector.py（プロジェクトルート）

import sys
import os

# srcディレクトリへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# メイン関数をインポートして実行
from src.main import main

if __name__ == "__main__":
    main()