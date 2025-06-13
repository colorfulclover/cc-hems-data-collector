# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-06-09

### Added
- **Data Collection Features**: Functionality to collect instantaneous power, instantaneous current, and cumulative power, as well as regular cumulative power readings every 30 minutes (EA) and power consumption over the last 30 minutes (EC).
- **Execution Modes**: Support for two execution modes: `schedule` (cron-style) and `interval` (fixed interval).
- **Diverse Output Options**: Support for output to `stdout`, `file`, `Google Cloud Pub/Sub`, and `webhook`; support for `json`, `yaml`, and `csv` formats; and the ability to specify multiple output destinations simultaneously.
- **Enhanced ECHONET Lite Compliance**: Strengthened compliance with specifications including interpretation of negative values for instantaneous power/current, automatic detection of single-phase/three-phase systems, and dynamic acquisition of cumulative power units.
- **Timezone Support**: Ability to specify the timezone of the data source, with all timestamps unified in UTC for output.
- **Packaging**: Introduction of `setuptools` for pip installation support.
- **Command-line Enhancements**: Addition of numerous options such as `--version` and `--debug`, with enhanced configuration via environment variables.
