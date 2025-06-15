# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] - 2025-06-15

### Added
- **Interactive Management Scripts**: Introduced `service-manager.sh` for easy, interactive installation, updates, and uninstallation of the service.
- **Makefile Support**: Added a `Makefile` to provide simple, one-word commands (`make install`, `make status`, etc.) for service management.
- **File Format Selection**: Users can now choose between `csv` and `json` formats for file-based output during installation and updates.

### Changed
- **Installation Process**: The installation flow has been significantly improved to be more robust and user-friendly, centered around the `service-manager.sh` script.
- **Configuration Update Logic**: The update process no longer reads from `.env` files and instead overwrites previous settings to ensure a predictable state.
- **Script Architecture**: Refactored shell scripts to eliminate dependencies on `.env` files for core logic, improving reliability.

### Fixed
- **Version Detection**: Corrected the file copy mechanism to include the `.git` directory, fixing `setuptools-scm` version detection errors during installation.
- **Interactive Prompt Display**: Resolved a bug where prompts in shell scripts were not displayed when their output was redirected.
- **Service File Generation**: Ensured that the `systemd` service file is always generated with the correct command-line arguments based on the user's selections.

## [0.1.0] - 2025-06-09

### Added
- **Data Collection Features**: Functionality to collect instantaneous power, instantaneous current, and cumulative power, as well as regular cumulative power readings every 30 minutes (EA) and power consumption over the last 30 minutes (EC).
- **Execution Modes**: Support for two execution modes: `schedule` (cron-style) and `interval` (fixed interval).
- **Diverse Output Options**: Support for output to `stdout`, `file`, `Google Cloud Pub/Sub`, and `webhook`; support for `json`, `yaml`, and `csv` formats; and the ability to specify multiple output destinations simultaneously.
- **Enhanced ECHONET Lite Compliance**: Strengthened compliance with specifications including interpretation of negative values for instantaneous power/current, automatic detection of single-phase/three-phase systems, and dynamic acquisition of cumulative power units.
- **Timezone Support**: Ability to specify the timezone of the data source, with all timestamps unified in UTC for output.
- **Packaging**: Introduction of `setuptools` for pip installation support.
- **Command-line Enhancements**: Addition of numerous options such as `--version` and `--debug`, with enhanced configuration via environment variables.
