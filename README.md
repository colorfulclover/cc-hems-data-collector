# HEMS Data Collector

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/)

[日本語版ドキュメントを読む（Read Japanese version）](README_JP.md)

`hems-data-collector` is a Python tool for collecting power consumption data from smart meters via the B-route and transmitting it to various destinations. It is designed to run stably as a background service on Linux systems like Raspberry Pi.

## Key Features

- **Stable Service Operation**: Runs as a `systemd` service, ensuring automatic startup on boot and automatic restarts in case of failure.
- **Easy Installation and Management**: An interactive script (`service-manager.sh`) simplifies installation, updates, and uninstallation.
- **Flexible Output Destinations**: Supports sending data to files (CSV/JSON), webhooks, and Google Cloud Pub/Sub.
- **Robust Data Collection**: Periodically collects a wide range of power data, including instantaneous power, cumulative consumption, and more.

## Output Data Format

The collected data is structured as a JSON object. For CSV output, the keys of this object are used as headers.

### JSON Format Example

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

### Field Descriptions

| Key                                 | Type         | Description                                                                                                   |
|:------------------------------------|:-------------|:--------------------------------------------------------------------------------------------------------------|
| `timestamp`                         | string       | Data collection time (UTC, ISO 8601 format).                                                                  |
| `cumulative_power_kwh`              | float        | Cumulative power consumption (kWh).                                                                           |
| `instant_power_w`                   | integer      | Instantaneous power (W).                                                                                      |
| `current_a`                         | float        | Representative current (A). For single-phase, this is the R-phase value; for three-phase, it's the sum of R and T phases. |
| `current_r_a`                       | float        | R-phase instantaneous current (A).                                                                            |
| `current_t_a`                       | float \| null| T-phase instantaneous current (A). For single-phase 2-wire systems, this is `null`.                         |
| `historical_timestamp`              | string       | Measurement time for regular cumulative power (UTC, ISO 8601 format). Typically at 30-minute intervals.       |
| `historical_cumulative_power_kwh`   | float        | Regular cumulative power consumption (kWh).                                                                   |
| `recent_30min_timestamp`            | string       | Measurement time for power consumption over the last 30 minutes (UTC, ISO 8601 format).                       |
| `recent_30min_consumption_kwh`      | float        | Power consumption over the last 30 minutes (kWh).                                                             |

## Prerequisites

- A Linux-based operating system (e.g., Raspberry Pi OS).
- Python 3.11 or higher.
- A Wi-SUN communication module (e.g., [RL7023 Stick-D/IPS](https://www.tessera.co.jp/product/rfmodul/rl7023stick-d_ips.html)).
- **Git**: Required to clone the source code.
- **Serial Port Access (for Linux)**:
  The user running the application must have permission to access the serial port. The installation script handles this by creating a dedicated user (`hems-data-collector`) and adding it to the `dialout` group.

## Installation

There are two ways to install the application, depending on your needs.

### 1. As a Service (Recommended)

This method installs the application as a `systemd` service that runs in the background.

1.  Clone the repository:
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  Run the installation script:
    ```bash
    sudo ./service-manager.sh install
    ```
    Alternatively, you can use the `Makefile`:
    ```bash
    make install
    ```
    The script will guide you through an interactive setup process for things like your B-route ID, password, and desired output destination.

### 2. For Development / Manual Use

This method is for developers who want to run the application manually or modify the source code.

1.  Clone the repository:
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  Create and activate a Python virtual environment (recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  Install the required packages:
    ```bash
    pip install -e .
    ```
    If you plan to use the Google Cloud Pub/Sub output, install the extra dependencies:
    ```bash
    pip install -e '.[gcloud]'
    ```

## Usage

### 1. Service Management

When installed as a service, use the `service-manager.sh` script to manage it:

- **Check Status**:
  ```bash
  sudo ./service-manager.sh status
  # or using make:
  make status
  ```
- **Update Configuration**:
  This command allows you to interactively change the output destination (e.g., from file to webhook).
  ```bash
  sudo ./service-manager.sh update
  # or using make:
  make update
  ```
- **Uninstall**:
  This removes the service, user, and all related files.
  ```bash
  sudo ./service-manager.sh uninstall
  # or using make:
  make uninstall
  ```

### 2. Direct Execution from the Command Line

For development, you can run the application directly. Make sure your virtual environment is activated.

- **Basic Example (Output to standard output in JSON format)**:
  ```bash
  hems-data-collector --output stdout
  ```
- **File Output Example**:
  ```bash
  hems-data-collector --output file --format csv --file data.csv
  ```
- **Debug Mode**:
  ```bash
  hems-data-collector --output stdout --debug
  ```

## Configuration

### 1. Service Configuration

When installed as a service, all settings are stored in `/opt/hems-data-collector/.env`.

- **Initial Setup**: Settings are configured interactively during the `install` process.
- **Updating Settings**: To change output-related settings, use the `sudo ./service-manager.sh update` command. For basic settings like `SERIAL_PORT` or `B_ROUTE_ID`, you can edit the `.env` file directly and then restart the service (`sudo systemctl restart hems-data-collector`).

### 2. Environment Variables

The application is configured via environment variables. For manual execution, you can create a `.env` file in the project root or set them in your shell.

| Environment Variable            | Description                                                                                                    | Default Value                            |
|:--------------------------------|:---------------------------------------------------------------------------------------------------------------|:-----------------------------------------|
| `SERIAL_PORT`                   | The serial port for the Wi-SUN module.                                                                         | `/dev/ttyUSB0`                           |
| `SERIAL_RATE`                   | The serial port's baud rate.                                                                                   | `115200`                                 |
| `B_ROUTE_ID`                    | Your B-route authentication ID.                                                                                | (None, required)                         |
| `B_ROUTE_PASSWORD`              | Your B-route password.                                                                                         | (None, required)                         |
| `LOCAL_TIMEZONE`                | The timezone for the data source. Use a standard `zoneinfo` name.                                                | `Asia/Tokyo`                             |
| `FILE_FORMAT`                   | The format for file output (`csv` or `json`). Used only when the output destination is set to `file`.             | `csv`                                    |
| `WEBHOOK_URL`                   | The destination URL for webhook output.                                                                        | (None)                                   |
| `GCP_PROJECT_ID`                | Your Google Cloud project ID.                                                                                  | (None)                                   |
| `GCP_TOPIC_NAME`                | The name of your Google Cloud Pub/Sub topic.                                                                   | (None)                                   |

### 3. Command-Line Options

These options are primarily for development and manual execution. They override any corresponding environment variables.

| Option                  | Short Form | Description                                                    | Default Value                                |
|:------------------------|:-----------|:---------------------------------------------------------------|:---------------------------------------------|
| `--help`                | `-h`       | Show help message and exit.                                    | -                                            |
| `--version`             | `-v`       | Show version information and exit.                             | -                                            |
| `--output`              | `-o`       | Output type (`stdout`, `file`, `gcloud`, `webhook`).           | `None`                                       |
| `--format`              | `-f`       | Output format (`json`, `yaml`, `csv`).                         | `json`                                       |
| `--file`                |            | Path for file output.                                          | `hems_data.dat`                              |
| `--port`                |            | Serial port for the Wi-SUN module.                             | (Value of `SERIAL_PORT` env var)             |
| `--baudrate`            |            | Serial port baud rate.                                         | (Value of `SERIAL_RATE` env var)             |
| `--webhook-url`         |            | Webhook destination URL.                                       | (Value of `WEBHOOK_URL` env var)             |
| `--gcp-project`         |            | Google Cloud project ID.                                       | (Value of `GCP_PROJECT_ID` env var)          |
| `--gcp-topic`           |            | Google Cloud Pub/Sub topic name.                               | (Value of `GCP_TOPIC_NAME` env var)          |
| `--mode`                |            | Execution mode (`schedule` or `interval`).                     | `schedule` (Not used in service mode)        |
| `--schedule`            | `-s`       | Data collection schedule (crontab format).                     | `*/5 * * * *` (Not used in service mode)     |
| `--interval`            | `-i`       | Data collection interval (seconds).                            | `300` (Not used in service mode)             |
| `--debug`               |            | Enable debug mode (outputs detailed logs).                     | `False`                                      |

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
