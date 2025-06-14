# HEMS Data Collector

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/)

[日本語版ドキュメントを読む（Read Japanese version）](README_JP.md)

`hems-data-collector` is a Python tool for collecting power data from smart meters (HEMS) via the B-route and outputting it in specified formats to various destinations.

## Key Features

- **Data Collection**: Connects to smart meters via Wi-SUN module to periodically collect instantaneous power, instantaneous current, cumulative power consumption, 30-minute regular cumulative power, and power consumption over the last 30 minutes.
- **Flexible Execution Timing**: Supports cron-like scheduled execution (`schedule` mode) and fixed interval execution (`interval` mode).
- **Multiple Output Destinations**: Collected data can be sent to standard output, files, Google Cloud Pub/Sub, and webhooks. Multiple output destinations can be specified simultaneously.
- **Selectable Output Formats**: Output data can be in `json`, `yaml`, or `csv` format.
- **Configuration Flexibility**: Main settings can be configured through environment variables or command-line arguments, allowing for flexible operation.

## Output Data Format

Collected data is output in the following JSON object format.
For CSV format, these keys are used as headers.
Instantaneous current keys are standardized for both single-phase and three-phase systems, with non-existent values represented as `null` (for JSON) or an empty string (for CSV).

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

| Key | Type | Description |
|:--- |:--- |:--- |
| `timestamp` | string | Data collection time (UTC, ISO 8601 format). |
| `cumulative_power_kwh` | float | Cumulative power consumption (kWh). |
| `instant_power_w` | integer | Instantaneous power (W). |
| `current_a` | float | Representative current (A). For single-phase, this is the R-phase value; for three-phase, it's the sum of R-phase and T-phase values. |
| `current_r_a` | float | R-phase instantaneous current (A). |
| `current_t_a` | float \| null | T-phase instantaneous current (A). For single-phase 2-wire systems, this is `null`. |
| `historical_timestamp` | string | Measurement time for regular cumulative power (UTC, ISO 8601 format). Typically at 30-minute intervals. |
| `historical_cumulative_power_kwh` | float | Regular cumulative power consumption (kWh). |
| `recent_30min_timestamp` | string | Measurement time for power consumption over the last 30 minutes (UTC, ISO 8601 format). |
| `recent_30min_consumption_kwh` | float | Power consumption over the last 30 minutes (kWh). |

## Operating Environment

- Python 3.11 or higher
- Wi-SUN communication module (e.g., [RL7023 Stick-D/IPS](https://www.tessera.co.jp/product/rfmodul/rl7023stick-d_ips.html))

## Prerequisites

- **Git**: Required to clone the source code.
- **Python 3.11 or higher and Pip**: Required for project execution and dependency management.
- **Serial port access rights (for Linux)**:
  To access the serial port connected to the Wi-SUN module, the user must belong to the `dialout` group. If not already a member, add yourself with the following command:
  ```bash
  sudo usermod -aG dialout $USER
  ```
  After running this command, you need to log out and log back in for the changes to take effect.

## Installation

### Manual Installation

1.  Clone the repository.
    ```bash
    git clone https://github.com/colorfulclover/cc-hems-data-collector.git
    cd cc-hems-data-collector
    ```

2.  Create and activate a Python virtual environment (recommended).
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  Install dependencies.
    ```bash
    pip install -e .
    ```
    If you want to use the Google Cloud Pub/Sub output feature, install the following additional dependencies:
    ```bash
    pip install -e '.[gcloud]'
    ```

### Service Installation

For Linux systems, you can install HEMS Data Collector as a systemd service for automatic startup and management:

1. Use the provided service management script:
   ```bash
   sudo ./service-manager.sh install
   ```
   This will guide you through the setup process, including:
   - Serial port configuration
   - B-route authentication settings
   - Output destination selection (file, webhook, or Google Cloud)
   - Timezone configuration

2. Alternatively, you can use the Makefile for simpler commands:
   ```bash
   make install
   ```

The service installation creates a dedicated user, sets up required directories, and configures the application to run as a systemd service.

## Configuration

Application behavior is primarily configured through environment variables. Create a `.env` file in the project root to specify configuration values, or set environment variables directly in your execution environment.

### Example `.env` File

```env
# Wi-SUN module settings
SERIAL_PORT=/dev/ttyUSB0
SERIAL_RATE=115200

# B-route authentication information
B_ROUTE_ID=YOUR_B_ROUTE_ID
B_ROUTE_PASSWORD=YOUR_B_ROUTE_PASSWORD

# Google Cloud Pub/Sub settings (if needed)
GCP_PROJECT_ID=your-gcp-project-id
GCP_TOPIC_NAME=hems-data

# Webhook settings (if needed)
WEBHOOK_URL=http://your-server.com/webhook

# Timezone settings (if needed, default is Asia/Tokyo)
LOCAL_TIMEZONE=Asia/Tokyo
```

### Environment Variables

| Environment Variable | Description | Default Value |
|:--- |:--- |:--- |
| `SERIAL_PORT` | Serial port to which the Wi-SUN module is connected. | `/dev/ttyUSB0` |
| `SERIAL_RATE` | Serial port baud rate. | `115200` |
| `B_ROUTE_ID` | B-route authentication ID. | `00000000000000000000000000000000` |
| `B_ROUTE_PASSWORD` | B-route password. | `00000000000000000000000000000000` |
| `GCP_PROJECT_ID` | Google Cloud project ID. | `your-project-id` |
| `GCP_TOPIC_NAME` | Google Cloud Pub/Sub topic name. | `hems-data` |
| `WEBHOOK_URL` | Webhook destination URL. | `http://localhost:8000/webhook` |
| `LOCAL_TIMEZONE` | Data source timezone. Specify using a name recognized by `zoneinfo`, such as `Asia/Tokyo`. | `Asia/Tokyo` |

## Usage

`hems-data-collector` is run from the command line.

### Basic Command

```bash
hems-data-collector [OPTIONS]
```

### Usage Examples

- **Output to standard output in JSON format (scheduled execution)**
  ```bash
  hems-data-collector --output stdout --format json
  ```

- **Output to file and webhook at 30-second intervals**
  ```bash
  hems-data-collector --mode interval --interval 30 --output file webhook --file data.csv --format csv
  ```
- **Output to Google Cloud Pub/Sub every 5 minutes**
  ```bash
  hems-data-collector --output gcloud --schedule "*/5 * * * *"
  ```

- **Run with debug logs enabled**
  ```bash
  hems-data-collector --output stdout --debug
  ```

### Service Management

If you installed the application as a service, you can manage it using the following commands:

```bash
# Check service status
sudo ./service-manager.sh status
# or
make status

# Update service configuration
sudo ./service-manager.sh update
# or
make update

# Uninstall the service
sudo ./service-manager.sh uninstall
# or
make uninstall
```

The service automatically starts at system boot and restarts on failure.

### Command-Line Options

| Option | Short Form | Description | Default Value |
|:--- |:--- |:--- |:--- |
| `--help` | `-h` | Display help message. | - |
| `--version` | `-v` | Display version information and exit. | - |
| `--output` | `-o` | Output type (`stdout`, `file`, `gcloud`, `webhook`). Multiple can be specified. | `None` (log output only) |
| `--format` | `-f` | Output format (`json`, `yaml`, `csv`). | `json` |
| `--file` | | Path for file output. | `hems_data.dat` |
| `--gcp-project` | | Google Cloud project ID. | (value of `GCP_PROJECT_ID` environment variable) |
| `--gcp-topic` | | Google Cloud Pub/Sub topic name. | (value of `GCP_TOPIC_NAME` environment variable) |
| `--webhook-url` | | Webhook destination URL. | (value of `WEBHOOK_URL` environment variable) |
| `--port` | | Serial port to which the Wi-SUN module is connected. | (value of `SERIAL_PORT` environment variable) |
| `--baudrate` | | Serial port baud rate. | (value of `SERIAL_RATE` environment variable) |
| `--meter-channel` | | Smart meter channel. If specified, skips scanning. | `None` |
| `--meter-panid` | | Smart meter PAN ID. If specified, skips scanning. | `None` |
| `--meter-ipv6` | | Smart meter IPv6 address. If specified, skips scanning. | `None` |
| `--mode` | | Execution mode (`schedule` or `interval`). | `schedule` |
| `--schedule` | `-s` | Data collection schedule (crontab format). Valid in `schedule` mode. | `*/5 * * * *` |
| `--interval` | `-i` | Data collection interval (seconds). Valid in `interval` mode. | `300` |
| `--debug` | | Enable debug mode (outputs detailed logs). | `False` |

## License

This project is released under the MIT License. See the `LICENSE` file for details.
