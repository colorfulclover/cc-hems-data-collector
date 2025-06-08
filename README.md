# HEMS Data Collector for Smart Meter

スマートメーターからECHONET Liteプロトコルを使用して電力消費量データを取得し、リアルタイムで出力するためのPython製クライアントツールです。
Wi-SUNモジュール（BP35A1など）を搭載したUSBドングルを介してスマートメーターと通信します。

## 概要

このツールは、家庭の電力使用状況を把握・分析したい開発者や研究者、ホビイストを対象としています。
スマートメーターから取得したデータを、標準出力、ファイル、またはGoogle Cloud Pub/Subへ柔軟に出力することができ、Home Energy Management System (HEMS) のデータ収集基盤として利用できます。

## 主な機能

- **スマートメーターからのデータ取得**:
  - 積算電力量 (kWh)
  - 瞬時電力 (W)
  - 瞬時電流 (R相, T相)
- **柔軟な出力先**:
  - 標準出力 (stdout)
  - ファイル (JSON, YAML, CSV)
  - Google Cloud Pub/Sub
- **豊富な設定オプション**:
  - コマンドライン引数と環境変数の両方で設定可能
  - データ取得間隔、シリアルポート、Bルート認証情報などを指定可能
- **堅牢な接続処理**:
  - ネットワークスキャンによる最適なチャンネル・PANの自動設定
  - PANAセッションの自動再接続機能

## 動作要件

- Python 3.9以上
- Wi-SUN USBドングル (例: [ローム BP35A1](https://www.rohm.co.jp/products/wireless-communication/sub-ghz-wireless-modules/bp35a1-product))
- スマートメーター (Bルートサービス対応)
- Bルート認証ID・パスワード (契約している電力会社から取得)

---

## インストール

### 1. リポジトリのクローン
```bash
git clone https://github.com/your-username/cc-hems-data-collector.git
cd cc-hems-data-collector
```

### 2. 仮想環境のセットアップ (推奨)
```bash
python3 -m venv venv
source venv/bin/activate
# Windowsの場合: venv\\Scripts\\activate
```

### 3. 依存関係のインストール
```bash
pip install -r requirements.txt
```
Google Cloud Pub/Subへ出力する場合は、追加でライブラリをインストールします。
```bash
pip install google-cloud-pubsub
```

---

## 設定

アプリケーションの動作は、環境変数またはコマンドライン引数で設定できます。両方が指定された場合は、コマンドライン引数が優先されます。

### 環境変数 (推奨)

以下の環境変数を設定することで、認証情報などを安全に管理できます。

| 変数名 | 説明 | デフォルト値 |
|:--- |:--- |:--- |
| `B_ROUTE_ID` | 電力会社から提供されるBルート認証ID。 | (なし) |
| `B_ROUTE_PASSWORD` | 電力会社から提供されるBルートパスワード。 | (なし) |
| `SERIAL_PORT` | Wi-SUNドングルが接続されているシリアルポート。 | `/dev/ttyUSB0` |
| `SERIAL_RATE` | シリアルポートのボーレート。 | `115200` |
| `GCP_PROJECT_ID` | Google Cloud Pub/Sub出力用のプロジェクトID。 | `your-project-id` |
| `GCP_TOPIC_NAME` | Google Cloud Pub/Sub出力用のトピック名。 | `hems-data` |

`.env`ファイルを使用する場合は、以下のように起動します。
```bash
# export $(cat .env | xargs) && python hems_data_collector.py
```

---

## 使い方

プロジェクトのルートディレクトリから`hems_data_collector.py`を実行します。

### 基本的な実行

`--output`オプションを指定しない場合、取得したデータはログとして標準エラーに出力されるのみで、ファイル等への書き出しは行われません。
```bash
python hems_data_collector.py
```

### 出力例

**JSON形式で標準出力する**
```bash
python hems_data_collector.py --output stdout --format json
```
出力サンプル:
```json
{"timestamp": "2023-10-27T10:00:00.123456", "cumulative_power": 12345.6, "instant_power": 500, "current_r": 2.5, "current_t": 2.5}
```

**CSV形式でファイルに出力する**
```bash
python hems_data_collector.py --output file --format csv --file power_data.csv
```
`power_data.csv` の内容:
```csv
timestamp,cumulative_power_kwh,instant_power_w,current_r_a,current_t_a
2023-10-27T10:00:00.123456,12345.6,500,2.5,2.5
2023-10-27T10:05:00.456789,12345.7,550,2.7,2.8
```

**Google Cloud Pub/Sub へ出力する**
```bash
python hems_data_collector.py --output cloud
```
(事前に`GCP_PROJECT_ID`と`GCP_TOPIC_NAME`環境変数の設定、または`gcloud auth application-default login`での認証が必要です)


### コマンドラインオプション

`python hems_data_collector.py --help`で詳細なオプションを確認できます。

| オプション | 説明 | デフォルト値 |
|:--- |:--- |:--- |
| `-h`, `--help` | ヘルプメッセージを表示 | |
| `-o`, `--output` | 出力タイプ (`stdout`, `file`, `cloud`, `all`)。 | `None` (ログ出力のみ) |
| `-f`, `--format` | 出力フォーマット (`json`, `yaml`, `csv`)。 | `json` |
| `--file` | ファイル出力時のパス。 | `hems_data.dat` |
| `--project` | Google CloudプロジェクトID。 | (環境変数またはconfig値) |
| `--topic` | Pub/Subトピック名。 | (環境変数またはconfig値) |
| `--port` | シリアルポート。 | (環境変数またはconfig値) |
| `--baudrate`| ボーレート。 | (環境変数またはconfig値) |
| `--meter-channel`| スマートメーターのチャンネル。 | (自動スキャン) |
| `--meter-panid`| スマートメーターのPAN ID。 | (自動スキャン) |
| `--meter-ipv6`| スマートメーターのIPv6アドレス。 | (自動スキャン) |
| `--mode` | 実行モード (`schedule` or `interval`)。 | `schedule` |
| `-s`, `--schedule`| データ取得スケジュール（crontab形式）。`schedule`モードで有効。 | `*/5 * * * *` |
| `-i`, `--interval`| データ取得間隔（秒）。`interval`モードで有効。 | `300` |
| `--debug` | デバッグモードを有効化（詳細ログ出力）。 | `False` |


---

## トラブルシューティング

- **接続できない**:
  - Wi-SUNドングルがPCに正しく認識されているか確認してください (`dmesg | grep tty`など)。
  - `--port`で正しいシリアルポートを指定しているか確認してください。
  - シリアルポートへのアクセス権限があるか確認してください (例: `sudo usermod -aG dialout $USER`)。
- **データ取得に失敗する (`FAIL ER04`など)**:
  - BルートID/パスワードが正しいか確認してください。
  - ドングルとスマートメーターの距離や、間の障害物など、電波環境を確認してください。
  - `--debug`オプションを付けて実行し、詳細なエラーログを確認してください。

## ライセンス

このプロジェクトは[MITライセンス](LICENSE)の下で公開されています。

## 貢献

プルリクエストは歓迎します。大きな変更を加える前には、まずissueを作成して議論してください。
