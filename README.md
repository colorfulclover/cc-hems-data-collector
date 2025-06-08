# HEMS Data Collector

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/)

`hems-data-collector`は、スマートメーター（HEMS）からBルート経由で電力データを収集し、指定された形式と先に出力するためのPython製ツールです。

## 主な機能

- **データ取得**: Wi-SUNモジュールを介してスマートメーターに接続し、瞬時電力、積算電力量、瞬時電流などを定期的に取得します。
- **柔軟な実行タイミング**: cronライクなスケジュール実行 (`schedule` モード)と、固定間隔での実行 (`interval` モード)をサポートします。
- **多様な出力先**: 取得したデータは、標準出力、ファイル、Google Cloud Pub/Sub、Webhookに送信できます。複数の出力先を同時に指定することも可能です。
- **選べる出力形式**: 出力データは `json`, `yaml`, `csv` から選択できます。
- **設定の柔軟性**: 主な設定は環境変数またはコマンドライン引数で行うことができ、柔軟な運用が可能です。

## 動作環境

- Python 3.11 以上
- Wi-SUN通信モジュール（例: [RL7023 Stick-D/IPS](https://www.tessera.co.jp/product/rfmodul/rl7023stick-d_ips.html)）

## 前提条件

- **Git**: ソースコードをクローンするために必要です。
- **Python 3.11以上およびPip**: プロジェクトの実行と依存関係の管理に必要です。
- **シリアルポートへのアクセス権 (Linuxの場合)**:
  Wi-SUNモジュールが接続されたシリアルポートにアクセスするために、ユーザーが `dialout` グループに所属している必要があります。所属していない場合は、以下のコマンドで追加してください。
  ```bash
  sudo usermod -aG dialout $USER
  ```
  このコマンドを実行した後は、一度ログアウトしてから再度ログインする必要があります。

## インストール

1.  リポジトリをクローンします。
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  Pythonの仮想環境を作成し、有効化します。（推奨）
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  依存パッケージをインストールします。
    ```bash
    pip install -e .
    ```
    Google Cloud Pub/Subへの出力機能を使用する場合は、追加で以下をインストールしてください。
    ```bash
    pip install -e '.[gcloud]'
    ```

## 設定

アプリケーションの動作は、主に環境変数で設定します。プロジェクトルートに `.env` ファイルを作成して設定値を記述するか、実行環境で直接環境変数を設定してください。

### `.env` ファイルの例

```env
# Wi-SUNモジュール設定
SERIAL_PORT=/dev/ttyUSB0
SERIAL_RATE=115200

# Bルート認証情報
B_ROUTE_ID=YOUR_B_ROUTE_ID
B_ROUTE_PASSWORD=YOUR_B_ROUTE_PASSWORD

# Google Cloud Pub/Sub 設定 (必要な場合)
GCP_PROJECT_ID=your-gcp-project-id
GCP_TOPIC_NAME=hems-data

# Webhook 設定 (必要な場合)
WEBHOOK_URL=http://your-server.com/webhook
```

### 環境変数一覧

| 環境変数 | 説明 | デフォルト値 |
|:--- |:--- |:--- |
| `SERIAL_PORT` | Wi-SUNモジュールが接続されているシリアルポート。 | `/dev/ttyUSB0` |
| `SERIAL_RATE` | シリアルポートのボーレート。 | `115200` |
| `B_ROUTE_ID` | Bルートの認証ID。 | `00000000000000000000000000000000` |
| `B_ROUTE_PASSWORD` | Bルートのパスワード。 | `00000000000000000000000000000000` |
| `GCP_PROJECT_ID` | Google CloudプロジェクトID。 | `your-project-id` |
| `GCP_TOPIC_NAME` | Google Cloud Pub/Subのトピック名。 | `hems-data` |
| `WEBHOOK_URL` | Webhookの送信先URL。 | `http://localhost:8000/webhook` |

## 使い方

`hems-data-collector` はコマンドラインから実行します。

### 基本的なコマンド

```bash
hems-data-collector [OPTIONS]
```

### 実行例

- **標準出力にJSON形式で出力する (スケジュール実行)**
  ```bash
  hems-data-collector --output stdout --format json
  ```

- **30秒間隔でファイルとWebhookに出力する**
  ```bash
  hems-data-collector --mode interval --interval 30 --output file webhook --file data.csv --format csv
  ```
- **Google Cloud Pub/Sub に5分ごとに出力する**
  ```bash
  hems-data-collector --output gcloud --schedule "*/5 * * * *"
  ```

- **デバッグログを有効にして実行**
  ```bash
  hems-data-collector --output stdout --debug
  ```

### コマンドラインオプション

| オプション | 短縮形 | 説明 | デフォルト値 |
|:--- |:--- |:--- |:--- |
| `--help` | `-h` | ヘルプメッセージを表示します。 | - |
| `--version` | `-v` | バージョン情報を表示して終了します。 | - |
| `--output` | `-o` | 出力タイプ (`stdout`, `file`, `gcloud`, `webhook`)。複数指定可。 | `None` (ログ出力のみ) |
| `--format` | `-f` | 出力フォーマット (`json`, `yaml`, `csv`)。 | `json` |
| `--file` | | ファイル出力時のパス。 | `hems_data.dat` |
| `--gcp-project` | | Google CloudプロジェクトID。 | (環境変数 `GCP_PROJECT_ID`の値) |
| `--gcp-topic` | | Google Cloud Pub/Subトピック名。 | (環境変数 `GCP_TOPIC_NAME`の値) |
| `--webhook-url` | | Webhookの送信先URL。 | (環境変数 `WEBHOOK_URL`の値) |
| `--port` | | Wi-SUNモジュールが接続されているシリアルポート。 | (環境変数 `SERIAL_PORT`の値) |
| `--baudrate` | | シリアルポートのボーレート。 | (環境変数 `SERIAL_RATE`の値) |
| `--meter-channel` | | スマートメーターのチャンネル。指定するとスキャンを省略。 | `None` |
| `--meter-panid` | | スマートメーターのPAN ID。指定するとスキャンを省略。 | `None` |
| `--meter-ipv6` | | スマートメーターのIPv6アドレス。指定するとスキャンを省略。 | `None` |
| `--mode` | | 実行モード (`schedule` または `interval`)。 | `schedule` |
| `--schedule` | `-s` | データ取得スケジュール（crontab形式）。`schedule`モードで有効。 | `*/5 * * * *` |
| `--interval` | `-i` | データ取得間隔（秒）。`interval`モードで有効。 | `300` |
| `--debug` | | デバッグモードを有効化（詳細なログを出力）。 | `False` |

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は `LICENSE` ファイルをご覧ください。
