# HEMS Data Collector

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/)

[英語版ドキュメントを読む（Read English version）](README.md)

`hems-data-collector`は、スマートメーター（HEMS）からBルート経由で電力データを収集し、指定された形式と先に出力するためのPython製ツールです。

## 主な機能

- **データ取得**: Wi-SUNモジュールを介してスマートメーターに接続し、瞬時電力、瞬時電流、積算電力量、30分ごとの定時積算電力量、直近30分間の消費電力量などを定期的に取得します。
- **柔軟な実行タイミング**: cronライクなスケジュール実行 (`schedule` モード)と、固定間隔での実行 (`interval` モード)をサポートします。
- **多様な出力先**: 取得したデータは、標準出力、ファイル、Google Cloud Pub/Sub、Webhookに送信できます。複数の出力先を同時に指定することも可能です。
- **選べる出力形式**: 出力データは `json`, `yaml`, `csv` から選択できます。
- **設定の柔軟性**: 主な設定は環境変数またはコマンドライン引数で行うことができ、柔軟な運用が可能です。

## 出力データフォーマット

取得されるデータは、以下のJSONオブジェクト形式で出力されます。
CSV形式の場合も、これらのキーがヘッダーとして使用されます。
単相と三相で瞬時電流のキーは共通化されており、存在しない値は `null` (JSONの場合)または空文字(CSVの場合)になります。

### JSON形式の例

```json
{
  "timestamp": "2023-10-27T10:00:00.123456+00:00",
  "cumulative_power_kwh": 12345.6,
  "instant_power_w": 500,
  "current_a": 7.5,
  "current_r_a": 5.0,
  "current_t_a": 2.5,
  "historical_timestamp": "2023-10-27T10:00:00+00:00",
  "historical_cumulative_power_kwh": 12345.5,
  "recent_30min_timestamp": "2023-10-27T09:30:00+00:00",
  "recent_30min_consumption_kwh": 0.2
}
```

### フィールド説明

| キー | 型 | 説明 |
|:--- |:--- |:--- |
| `timestamp` | string | データ取得時刻 (UTC, ISO 8601形式)。 |
| `cumulative_power_kwh` | float | 積算電力量 (kWh)。 |
| `instant_power_w` | integer | 瞬時電力 (W)。 |
| `current_a` | float | 代表電流 (A)。単相時はR相の値、三相時はR相とT相の合計値。 |
| `current_r_a` | float | R相の瞬時電流 (A)。 |
| `current_t_a` | float \| null | T相の瞬時電流 (A)。単相2線式の場合は `null`。 |
| `historical_timestamp` | string | 定時積算電力量の計測時刻 (UTC, ISO 8601形式)。通常は30分ごとの時刻。 |
| `historical_cumulative_power_kwh` | float | 定時積算電力量 (kWh)。 |
| `recent_30min_timestamp` | string | 直近30分間の消費電力量の計測時刻 (UTC, ISO 8601形式)。 |
| `recent_30min_consumption_kwh` | float | 直近30分間の消費電力量 (kWh)。 |

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

### 手動インストール

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

### サービスとしてのインストール

Linuxシステムでは、HEMS Data Collectorをsystemdサービスとしてインストールして自動起動と管理を行うことができます：

1. 提供されているサービス管理スクリプトを使用します：
   ```bash
   sudo ./service-manager.sh install
   ```
   このコマンドは以下を含むセットアッププロセスをガイドします：
   - シリアルポートの設定
   - Bルート認証設定
   - 出力先の選択（ファイル、webhook、またはGoogle Cloud）
   - タイムゾーン設定

2. あるいは、より簡単なコマンドを使用するためにMakefileを使用することもできます：
   ```bash
   make install
   ```

サービスインストールは、専用ユーザーの作成、必要なディレクトリの設定、そしてアプリケーションをsystemdサービスとして実行するための設定を行います。

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

# タイムゾーン設定 (必要な場合、デフォルトは Asia/Tokyo)
LOCAL_TIMEZONE=Asia/Tokyo
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
| `LOCAL_TIMEZONE` | データ取得元のタイムゾーン。`Asia/Tokyo`など`zoneinfo`が認識する名前で指定。 | `Asia/Tokyo` |

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

### サービス管理

アプリケーションをサービスとしてインストールした場合、以下のコマンドで管理できます：

```bash
# サービスの状態確認
sudo ./service-manager.sh status
# または
make status

# サービス設定の更新
sudo ./service-manager.sh update
# または
make update

# サービスのアンインストール
sudo ./service-manager.sh uninstall
# または
make uninstall
```

サービスはシステム起動時に自動的に開始され、障害が発生した場合は再起動します。

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
