# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - YYYY-MM-DD

### Added
- **スケジュール/インターバル実行**: `schedule` (cron形式) と `interval` (秒単位) の2つの実行モードを導入。
- **多様な出力先**: データを `stdout`, `file`, `Google Cloud Pub/Sub`, `webhook` に出力する機能を追加。
- **柔軟な出力形式**: `json`, `yaml`, `csv` の出力フォーマットをサポート。
- **定時積算電力量の取得**: 30分ごとの定時積算電力量を取得する機能を追加。
- **UTCタイムスタンプ**: ログとデータに含まれるタイムスタンプを全てUTCに統一。
- **ロギング改善**: ログフォーマットをUTCのISO 8601形式に統一し、デバッグモード (`--debug`) を追加。
- **コマンドライン引数の強化**:
    - 出力先を複数選択可能に (`--output stdout file`など)。
    - Google Cloud関連の引数を `--gcp-project`, `--gcp-topic` に変更。
    - メーター情報を直接指定 (`--meter-channel`等) することでスキャンを省略する機能を追加。
- **バージョン表示**: `--version` (`-v`) オプションを追加。
