# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-05-22

### Added
- **データ取得機能**: 瞬時電力、瞬時電流、積算電力量に加え、30分ごとの定時積算電力量(EA)、直近30分間の消費電力量(EC)を取得する機能。
- **実行モード**: `schedule` (cron形式) と `interval` (固定間隔) の2つの実行モードをサポート。
- **多様な出力**: `stdout`, `file`, `Google Cloud Pub/Sub`, `webhook`への出力、`json`, `yaml`, `csv`形式のサポート、および複数出力先の同時指定に対応。
- **ECHONET Lite準拠強化**: 瞬時電力・電流の負値解釈、単相・三相の自動判別、積算電力量単位の動的取得など、仕様への準拠を強化。
- **タイムゾーン対応**: データ取得元のタイムゾーンを指定可能にし、全てのタイムスタンプをUTCに統一して出力。
- **パッケージング**: `setuptools`を導入し、pipでのインストールに対応。
- **コマンドライン拡充**: `--version`, `--debug`など、多数のオプションを追加し、環境変数での設定を強化。
