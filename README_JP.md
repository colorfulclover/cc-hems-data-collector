# HEMS Data Collector

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/)

[Read English version (英語版ドキュメントを読む)](README.md)

`hems-data-collector`は、スマートメーターからBルート経由で電力消費データを収集し、様々な宛先に送信するためのPython製ツールです。Linuxシステム上で、バックグラウンドサービスとして安定稼働するように設計されています。

## 主な特徴

- **安定したサービス動作**: `systemd`のサービスとして動作し、システムの起動時に自動起動し、障害発生時には自動的に再起動します。
- **簡単なインストールと管理**: 対話形式のスクリプト (`service-manager.sh`) により、インストール、更新、アンインストールが簡単に行えます。
- **柔軟な出力先**: ファイル（CSV/JSON）、Webhook、Google Cloud Pub/Subへのデータ送信をサポートします。
- **堅牢なデータ収集**: 瞬時電力や積算電力量など、広範な電力データを定期的に収集します。

## 出力データフォーマット

収集されたデータはJSONオブジェクトとして構成されます。CSV形式で出力する場合、このオブジェクトのキーがヘッダーとして使用されます。

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

| キー                                | 型           | 説明                                                                                                 |
|:------------------------------------|:-------------|:-----------------------------------------------------------------------------------------------------|
| `timestamp`                         | string       | データ取得時刻（UTC, ISO 8601形式）。                                                                |
| `cumulative_power_kwh`              | float        | 積算電力量（kWh）。                                                                                  |
| `instant_power_w`                   | integer      | 瞬時電力（W）。                                                                                      |
| `current_a`                         | float        | 代表電流（A）。単相時はR相の値、三相時はR相とT相の合計値。                                            |
| `current_r_a`                       | float        | R相の瞬時電流（A）。                                                                                 |
| `current_t_a`                       | float \| null| T相の瞬時電流（A）。単相2線式の場合は`null`。                                                        |
| `historical_timestamp`              | string       | 定時積算電力量の計測時刻（UTC, ISO 8601形式）。通常は30分ごとの時刻。                                |
| `historical_cumulative_power_kwh`   | float        | 定時積算電力量（kWh）。                                                                              |
| `recent_30min_timestamp`            | string       | 直近30分間の消費電力量の計測時刻（UTC, ISO 8601形式）。                                              |
| `recent_30min_consumption_kwh`      | float        | 直近30分間の消費電力量（kWh）。                                                                      |

## 前提条件

- Linuxベースのオペレーティングシステム。
- Python 3.11 以上。
- Wi-SUN通信モジュール（例: [RL7023 Stick-D/IPS](https://www.tessera.co.jp/product/rfmodul/rl7023stick-d_ips.html)）。
- **Git**: ソースコードをクローンするために必要です。
- **シリアルポートへのアクセス権 (Linux)**:
  アプリケーションを実行するユーザーは、シリアルポートにアクセスする権限が必要です。インストールスクリプトは、専用ユーザー（`hems-data-collector`）を作成し、`dialout`グループに追加することでこれを処理します。

## インストール

用途に応じて2つのインストール方法があります。

### 1. サービスとしての利用（推奨）

この方法では、アプリケーションをバックグラウンドで動作する`systemd`サービスとしてインストールします。

1.  リポジトリをクローンします:
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  インストールスクリプトを実行します:
    ```bash
    sudo ./service-manager.sh install
    ```
    または、`Makefile`を使用することもできます:
    ```bash
    make install
    ```
    スクリプトがBルートID、パスワード、希望する出力先などの対話的なセットアッププロセスを案内します。

### 2. 開発・手動での利用

この方法は、アプリケーションを手動で実行したり、ソースコードを変更したりする開発者向けです。

1.  リポジトリをクローンします:
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  Pythonの仮想環境を作成し、有効化します（推奨）:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  必要なパッケージをインストールします:
    ```bash
    pip install -e .
    ```
    Google Cloud Pub/Subへの出力を使用する場合は、追加の依存関係をインストールしてください:
    ```bash
    pip install -e '.[gcloud]'
    ```

## 使い方

### 1. サービス管理

サービスとしてインストールした場合、`service-manager.sh`スクリプトを使用して管理します:

- **状態の確認**:
  ```bash
  sudo ./service-manager.sh status
  # または make を使用:
  make status
  ```
- **設定の更新**:
  このコマンドで、出力先（例: ファイルからWebhookへ）を対話的に変更できます。
  ```bash
  sudo ./service-manager.sh update
  # または make を使用:
  make update
  ```
- **アンインストール**:
  サービス、ユーザー、および関連するすべてのファイルを削除します。
  ```bash
  sudo ./service-manager.sh uninstall
  # または make を使用:
  make uninstall
  ```

### 2. コマンドラインからの直接実行

開発目的の場合、アプリケーションを直接実行できます。仮想環境が有効になっていることを確認してください。

- **基本的な例（JSON形式で標準出力に出力）**:
  ```bash
  hems-data-collector --output stdout
  ```
- **ファイル出力の例**:
  ```bash
  hems-data-collector --output file --format csv --file data.csv
  ```
- **デバッグモード**:
  ```bash
  hems-data-collector --output stdout --debug
  ```

## 設定

### 1. サービスの設定

サービスとしてインストールした場合、すべての設定は`/opt/hems-data-collector/.env`に保存されます。

- **初期設定**: `install`プロセス中に設定が対話的に構成されます。
- **設定の更新**: 出力関連の設定を変更するには、`sudo ./service-manager.sh update`コマンドを使用します。`SERIAL_PORT`や`B_ROUTE_ID`のような基本設定は、`.env`ファイルを直接編集してからサービスを再起動（`sudo systemctl restart hems-data-collector`）することで変更できます。

### 2. 環境変数

アプリケーションは環境変数を介して設定されます。手動で実行する場合、プロジェクトのルートに`.env`ファイルを作成するか、シェルで設定します。

| 環境変数                  | 説明                                                                                      | デフォルト値                             |
|:--------------------------|:------------------------------------------------------------------------------------------|:-----------------------------------------|
| `SERIAL_PORT`             | Wi-SUNモジュール用のシリアルポート。                                                      | `/dev/ttyUSB0`                           |
| `SERIAL_RATE`             | シリアルポートのボーレート。                                                              | `115200`                                 |
| `B_ROUTE_ID`              | Bルート認証ID。                                                                           | (なし、必須)                             |
| `B_ROUTE_PASSWORD`        | Bルートパスワード。                                                                       | (なし、必須)                             |
| `LOCAL_TIMEZONE`          | データソースのタイムゾーン。標準の`zoneinfo`名を使用してください。                        | `Asia/Tokyo`                             |
| `FILE_FORMAT`             | ファイル出力の形式（`csv`または`json`）。出力先が`file`に設定されている場合のみ使用。      | `csv`                                    |
| `WEBHOOK_URL`             | Webhook出力の送信先URL。                                                                  | (なし)                                   |
| `GCP_PROJECT_ID`          | Google CloudプロジェクトID。                                                              | (なし)                                   |
| `GCP_TOPIC_NAME`          | Google Cloud Pub/Subトピック名。                                                          | (なし)                                   |

### 3. コマンドラインオプション

これらのオプションは主に開発および手動実行用です。対応する環境変数よりも優先されます。

| オプション                | 短縮形     | 説明                                                           | デフォルト値                                 |
|:--------------------------|:-----------|:---------------------------------------------------------------|:---------------------------------------------|
| `--help`                  | `-h`       | ヘルプメッセージを表示して終了します。                         | -                                            |
| `--version`               | `-v`       | バージョン情報を表示して終了します。                           | -                                            |
| `--output`                | `-o`       | 出力タイプ（`stdout`, `file`, `gcloud`, `webhook`）。          | `None`                                       |
| `--format`                | `-f`       | 出力フォーマット（`json`, `yaml`, `csv`）。                    | `json`                                       |
| `--file`                  |            | ファイル出力のパス。                                           | `hems_data.dat`                              |
| `--port`                  |            | Wi-SUNモジュール用のシリアルポート。                           | （`SERIAL_PORT`環境変数の値）                |
| `--baudrate`              |            | シリアルポートのボーレート。                                   | （`SERIAL_RATE`環境変数の値）                |
| `--webhook-url`           |            | Webhookの送信先URL。                                           | （`WEBHOOK_URL`環境変数の値）                |
| `--gcp-project`           |            | Google CloudプロジェクトID。                                   | （`GCP_PROJECT_ID`環境変数の値）             |
| `--gcp-topic`             |            | Google Cloud Pub/Subトピック名。                               | （`GCP_TOPIC_NAME`環境変数の値）              |
| `--mode`                  |            | 実行モード（`schedule`または`interval`）。                    | `schedule`（サービスモードでは未使用）       |
| `--schedule`              | `-s`       | データ収集スケジュール（crontab形式）。                        | `*/5 * * * *`（サービスモードでは未使用）    |
| `--interval`              | `-i`       | データ収集間隔（秒）。                                         | `300`（サービスモードでは未使用）            |
| `--debug`                 |            | デバッグモードを有効化（詳細なログを出力）。                   | `False`                                      |

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は`LICENSE`ファイルをご覧ください。
