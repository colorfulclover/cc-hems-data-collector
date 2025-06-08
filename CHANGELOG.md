# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https.://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https.://semver.org/spec/v2.0.0.html).

## [0.1.0] - YYYY-MM-DD

### Added
- **スケジュール/インターバル実行**: `schedule` (cron形式) と `interval` (秒単位) の2つの実行モードを導入。
- **多様な出力先**: データを `stdout`, `file`, `Google Cloud Pub/Sub`, `webhook` に出力する機能を追加。
- **柔軟な出力形式**: `json`, `yaml`, `csv` の出力フォーマットをサポート。
- **UTCタイムスタンプ**: ログとデータに含まれるタイムスタンプを全てUTCに統一。
- **ロギング改善**: ログフォーマットをUTCのISO 8601形式に統一し、デバッグモード (`--debug`) を追加。
- **コマンドライン引数の強化**:
    - 出力先を複数選択可能に (`--output stdout file`など)。
    - Google Cloud関連の引数を `--gcp-project`, `--gcp-topic` に変更。
    - メーター情報を直接指定 (`--meter-channel`等) することでスキャンを省略する機能を追加。
- **バージョン表示**: `--version` (`-v`) オプションを追加。

### Changed
- **依存関係**: `croniter`, `requests` を追加。
- **設定方法**: 環境変数とコマンドライン引数による設定を主とし、設定ファイルへの依存を低減。
- **プロジェクト構成**: ロガー設定を `src/logger_config.py` に分離。

### Fixed
- **瞬時電流の計算**: 三相瞬時電流のR相とT相の値を正しくパースするように修正。
- **起動タイミング**: `schedule` モードでは、次回のスケジュール時刻まで待機してから最初のデータ取得を行うように修正。
- **CSVヘッダー**: ハードコードされていたCSVヘッダーを、設定ファイルで定義されたものを使用するように修正。 