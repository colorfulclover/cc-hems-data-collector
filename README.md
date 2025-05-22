# HEMS データ取得システム（ECHONET Lite クライアント）

スマートメーターから ECHONET Lite プロトコルを使用して HEMS（Home Energy Management System）データを取得し、複数の形式で出力するツールです。このクライアントは、USBトングル（BP35A1など）を使用してスマートメーターと通信します。

## 特徴

- スマートメーターからリアルタイムにデータを取得
- 複数の出力形式に対応：JSON、YAML、CSV
- 柔軟な出力先の選択：
  - 標準出力
  - ファイル出力
  - Google Cloud Pub/Sub
- 定期的なデータ取得間隔の設定
- 低消費電力で連続稼働可能

## 必要なもの

- Python 3.6以上
- Wi-SUNトングル（例：BP35A1）
- Bルート認証ID・パスワード（電力会社から取得）
- 対応するスマートメーター

## ディレクトリ構成
```text
hems-client/
│
├── requirements.txt        # 依存パッケージリスト
├── setup.py                # セットアップスクリプト（オプション）
├── README.md               # プロジェクト説明
├── hems_data_collector.py  # プロジェクトルートからの実行スクリプト
│
└── src/                    # ソースコードディレクトリ
    ├── __init__.py         # Pythonパッケージ化
    ├── main.py             # メインスクリプト
    ├── config.py           # 設定値の管理
    ├── serial_client.py    # シリアル通信とスマートメーター制御
    ├── output_handler.py   # 出力処理
    └── utils.py            # ユーティリティ関数

```


## インストール方法

### 1. リポジトリのクローン
```shell
git clone https://github.com/colorfulclover/hems-data-collector.git
cd hems-data-collector
```

### 2. 仮想環境のセットアップ（推奨）
```shell
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化（Linux/Mac）
source venv/bin/activate

# 仮想環境の有効化（Windows）
venv\Scripts\activate.bat
```

### 3. 依存パッケージのインストール
```shell
pip install -r requirements.txt
```

### 4. Bルート認証情報の設定
環境変数として設定（推奨）:
```shell
export B_ROUTE_ID="your_b_route_id"
export B_ROUTE_PASSWORD="your_b_route_password"
```
または、 `src/config.py` ファイル内で直接編集することもできます。 

### 5. シリアルポートの設定
USBトングルを接続し、シリアルポートを確認してください。デフォルトでは `/dev/ttyUSB0` を使用しますが、環境に合わせて `src/config.py` で変更するか、コマンドラインオプションで指定できます。 

## 使用方法
### 基本的な使い方
```shell
# プロジェクトルートから実行
./hems_data_collector.py

# または
python hems_data_collector.py
```

### 出力形式の選択
```shell
# JSON形式で標準出力（デフォルト）
python hems_client.py

# CSV形式で標準出力
python hems_client.py --format csv

# YAML形式でファイル出力
python hems_client.py --output file --format yaml --file hems_data.yaml
```

### 出力先の選択
```shell
# 標準出力（デフォルト）
python hems_client.py --output stdout

# ファイル出力
python hems_client.py --output file --file hems_data.json

# Google Cloud Pub/Sub出力
python hems_client.py --output cloud --project your-project-id --topic hems-data

# 全ての出力先に同時出力
python hems_client.py --output all
```

### その他のオプション
```shell
# データ取得間隔を1分（60秒）に設定
python hems_client.py --interval 60

# デバッグモードで実行（詳細ログ）
python hems_client.py --debug

# シリアルポートを指定
python hems_client.py --port /dev/ttyACM0
```

### 全オプション一覧
```shell
python hems_client.py --help
```
以下のようなヘルプが表示されます：
```shell
usage: hems_client.py [-h] [--output {stdout,file,cloud,all}] 
                      [--format {json,yaml,csv}] [--file FILE]
                      [--project PROJECT] [--topic TOPIC] [--port PORT]
                      [--baudrate BAUDRATE] [--interval INTERVAL] [--debug]

HEMSデータ取得ツール

optional arguments:
  -h, --help            ヘルプメッセージの表示
  --output {stdout,file,cloud,all}, -o {stdout,file,cloud,all}
                        出力タイプ (デフォルト: stdout)
  --format {json,yaml,csv}, -f {json,yaml,csv}
                        出力フォーマット (デフォルト: json)
  --file FILE           ファイル出力パス (デフォルト: hems_data.dat)
  --project PROJECT     Google Cloudプロジェクト
  --topic TOPIC         Pub/Subトピック名
  --port PORT           シリアルポート
  --baudrate BAUDRATE   ボーレート
  --interval INTERVAL, -i INTERVAL
                        データ取得間隔（秒）
  --debug               デバッグモードを有効化
```

## 取得データ
以下のデータを取得します：
- 積算電力量（kWh）
- 瞬時電力（W）
- 瞬時電流（A）- 単相または三相（R相、T相）

### 出力例（JSON）
```json
{
  "timestamp": "2023-06-15T15:23:42.123456",
  "cumulative_power": 12345.6,
  "instant_power": 1234,
  "current_r": 5.4,
  "current_t": 5.2
}
```

## Google Cloud Pub/Sub出力
Google Cloud Pub/Subを使用するには、追加のセットアップが必要です：
1. Google Cloud Pub/Subライブラリをインストール：
```shell
pip install google-cloud-pubsub
```

2. Google Cloud認証情報の設定：
```shell
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-project-credentials.json"
```

3. プロジェクトIDとトピック名の設定：
```shell
export GCP_PROJECT_ID="your-project-id"
export GCP_TOPIC_NAME="hems-data"
```

## 注意点
1. **Bルート認証情報**: 実際の認証情報は電力会社から取得する必要があります。
2. **シリアルポート**: 使用するシリアルポートは環境によって異なります。
3. **スマートメーターの応答**: 各スマートメーターの仕様によって応答フォーマットが異なる場合があります。
4. **セキュリティ**: Bルート認証情報は機密情報なので、環境変数での設定を推奨します。

## トラブルシューティング
- **接続エラー**: USBトングルが正しく接続されているか、シリアルポートの設定が正しいか確認してください。
- **認証エラー**: Bルート認証情報が正しいか確認してください。
- **データ取得エラー**: `--debug` オプションを使用して詳細なログを確認してください。
- **パーミッションエラー**: シリアルポートへのアクセス権限を確認してください。必要に応じて `sudo` を使用するか、ユーザーをダイアルアウトグループに追加してください。

## 今後の予定
- TBD

## ライセンス
MIT
## 貢献
プルリクエストは歓迎します。大きな変更を加える前には、まずissueを作成して議論してください。
