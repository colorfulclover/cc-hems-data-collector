#!/bin/bash

# HEMS Data Collector Common Utility Functions

# Initialization process
initialize() {
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
  INSTALL_DIR="/opt/hems-data-collector"
  DATA_DIR="/var/lib/hems-data"
  SERVICE_NAME="hems-data-collector"
  SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

  # Root permission check
  if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run with root privileges."
    echo "Please run: sudo $0 $1"
    exit 1
  fi
}

# Generate service file
generate_service_file() {
  # Receive command arguments from parameters
  local output_type="$1"
  local command_args=""

  # Set command arguments according to output type
  case "$output_type" in
    "webhook")
      command_args="--output webhook"
      ;;
    "gcloud")
      command_args="--output gcloud"
      ;;
    *)
      # Default is file output
      output_type="file"
      command_args="--output file --format csv --file /var/log/hems/data.csv"
      ;;
  esac

  # Generate service file
  cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=HEMS Data Collector Service
After=network.target

[Service]
Type=simple
User=${SERVICE_NAME}
Group=${SERVICE_NAME}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/hems-data-collector ${command_args}
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

  chmod 644 "${SERVICE_FILE}"
  echo "Generated service file based on configuration at ${SERVICE_FILE}"
}

# Create environment variable file
create_env_file() {
  local serial_port="$1"
  local serial_rate="$2"
  local b_route_id="$3"
  local b_route_password="$4"
  local output_choice="$5"
  local webhook_url="$6"
  local gcp_project_id="$7"
  local gcp_topic_name="$8"
  local timezone="$9"

  # Convert output type to string
  local output_type="file"
  case $output_choice in
    2) output_type="webhook" ;;
    3) output_type="gcloud" ;;
    *) output_type="file" ;;
  esac

  # Basic settings
  cat > "${INSTALL_DIR}/.env" << EOF
# Wi-SUN module settings
SERIAL_PORT=${serial_port}
SERIAL_RATE=${serial_rate}

# B-route authentication information
B_ROUTE_ID=${b_route_id}
B_ROUTE_PASSWORD=${b_route_password}

# Timezone settings
LOCAL_TIMEZONE=${timezone}
EOF



  # Add settings according to the selected output type
  case $output_choice in
    2)
      cat >> "${INSTALL_DIR}/.env" << EOF

# Webhook settings
WEBHOOK_URL=${webhook_url}
EOF
      ;;
    3)
      cat >> "${INSTALL_DIR}/.env" << EOF

# Google Cloud Pub/Sub settings
GCP_PROJECT_ID=${gcp_project_id}
GCP_TOPIC_NAME=${gcp_topic_name}
EOF
      ;;
  esac

  chown ${SERVICE_NAME}:${SERVICE_NAME} "${INSTALL_DIR}/.env"
  chmod 600 "${INSTALL_DIR}/.env"
  echo "Created environment variable configuration file at ${INSTALL_DIR}/.env"

  # サービスファイルを生成
  generate_service_file "$output_type"
}

# User interaction - collect settings
collect_settings() {
  # Serial port settings
  read -p "Wi-SUN module serial port [/dev/ttyUSB0]: " serial_port
  serial_port=${serial_port:-/dev/ttyUSB0}

  read -p "Serial port baud rate [115200]: " serial_rate
  serial_rate=${serial_rate:-115200}

  # B-route authentication information
  read -p "B-route authentication ID: " b_route_id
  while [ -z "$b_route_id" ]; do
    echo "B-route authentication ID is required."
    read -p "B-route authentication ID: " b_route_id
  done

  read -p "B-route password: " b_route_password
  while [ -z "$b_route_password" ]; do
    echo "B-route password is required."
    read -p "B-route password: " b_route_password
  done

  # Output type selection
  echo "\nPlease select the data output destination:"
  echo "1) File output (default)"
  echo "2) Webhook"
  echo "3) Google Cloud Pub/Sub"
  read -p "Selection [1-3]: " output_choice
  output_choice=${output_choice:-1}

  # Initial settings (default: file output)
  webhook_url=""
  gcp_project_id=""
  gcp_topic_name=""

  # Additional settings according to the selected output type
  case $output_choice in
    1)
      echo "File output selected."
      ;;
    2)
      echo "Webhook output selected."
      read -p "Webhook URL: " webhook_url
      while [ -z "$webhook_url" ]; do
        echo "Webhook URL is required."
        read -p "Webhook URL: " webhook_url
      done
      ;;
    3)
      echo "Google Cloud Pub/Sub output selected."
      read -p "GCP Project ID: " gcp_project_id
      while [ -z "$gcp_project_id" ]; do
        echo "GCP Project ID is required."
        read -p "GCP Project ID: " gcp_project_id
      done

      read -p "Pub/Sub topic name [hems-data]: " gcp_topic_name
      gcp_topic_name=${gcp_topic_name:-hems-data}
      ;;
    *)
      echo "Invalid selection. Using default file output."
      output_choice=1
      ;;
  esac

  # Timezone settings
  read -p "Timezone [Asia/Tokyo]: " timezone
  timezone=${timezone:-Asia/Tokyo}

  # 設定値を返す
  echo "${serial_port},${serial_rate},${b_route_id},${b_route_password},${output_choice},${webhook_url},${gcp_project_id},${gcp_topic_name},${timezone}"
}

# Update settings
update_settings() {
  # 現在の設定を読み込む
  source "${INSTALL_DIR}/.env"

  # Output type selection
  echo "\nPlease select the data output destination:"
  echo "1) File output"
  echo "2) Webhook"
  echo "3) Google Cloud Pub/Sub"
  read -p "Selection [1-3]: " output_choice


  # Additional settings according to the selected output type
  case $output_choice in
    1)
      echo "File output selected."

      # Update environment variables
      sed -i '/WEBHOOK_URL=/d' "${INSTALL_DIR}/.env"
      sed -i '/GCP_PROJECT_ID=/d' "${INSTALL_DIR}/.env"
      sed -i '/GCP_TOPIC_NAME=/d' "${INSTALL_DIR}/.env"
      ;
      webhook_url=""
      gcp_project_id=""
      gcp_topic_name=""
      ;;
    2)
      echo "Webhook output selected."
      read -p "Webhook URL [${WEBHOOK_URL:-}]: " webhook_url
      webhook_url=${webhook_url:-${WEBHOOK_URL:-}}

      # Update environment variables
      sed -i '/GCP_PROJECT_ID=/d' "${INSTALL_DIR}/.env"
      sed -i '/GCP_TOPIC_NAME=/d' "${INSTALL_DIR}/.env"
      gcp_project_id=""
      gcp_topic_name=""
      ;;
    3)
      echo "Google Cloud Pub/Sub output selected."
      read -p "GCP Project ID [${GCP_PROJECT_ID:-}]: " gcp_project_id
      gcp_project_id=${gcp_project_id:-${GCP_PROJECT_ID:-}}
      read -p "Pub/Sub topic name [${GCP_TOPIC_NAME:-hems-data}]: " gcp_topic_name
      gcp_topic_name=${gcp_topic_name:-${GCP_TOPIC_NAME:-hems-data}}

      # Update environment variables
      sed -i '/WEBHOOK_URL=/d' "${INSTALL_DIR}/.env"
      webhook_url=""
      ;;
    *)
      echo "Output settings were not changed."
      return 1
      ;;
  esac

  # Convert output type to string
  local output_type="file"
  case $output_choice in
    2) output_type="webhook" ;;
    3) output_type="gcloud" ;;
    *) output_type="file" ;;
  esac


  # Add output type specific settings
  case $output_choice in
    2)
      if grep -q "WEBHOOK_URL=" "${INSTALL_DIR}/.env"; then
        sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=${webhook_url}|" "${INSTALL_DIR}/.env"
      else
        echo "WEBHOOK_URL=${webhook_url}" >> "${INSTALL_DIR}/.env"
      fi
      ;;
    3)
      if grep -q "GCP_PROJECT_ID=" "${INSTALL_DIR}/.env"; then
        sed -i "s/GCP_PROJECT_ID=.*/GCP_PROJECT_ID=${gcp_project_id}/" "${INSTALL_DIR}/.env"
      else
        echo "GCP_PROJECT_ID=${gcp_project_id}" >> "${INSTALL_DIR}/.env"
      fi
      if grep -q "GCP_TOPIC_NAME=" "${INSTALL_DIR}/.env"; then
        sed -i "s/GCP_TOPIC_NAME=.*/GCP_TOPIC_NAME=${gcp_topic_name}/" "${INSTALL_DIR}/.env"
      else
        echo "GCP_TOPIC_NAME=${gcp_topic_name}" >> "${INSTALL_DIR}/.env"
      fi
      ;;
  esac

  echo "Output settings have been updated."

  # サービスファイルを再生成
  generate_service_file "$output_type"

  # Reload systemd configuration
  systemctl daemon-reload
  echo "Service configuration file has been updated. Please restart the service."

  # 設定値を返す
  echo "${output_choice},${webhook_url},${gcp_project_id},${gcp_topic_name}"
}

# Load settings from environment variables
load_settings_from_env() {
  # Return error if environment variable file doesn't exist
  if [ ! -f "${INSTALL_DIR}/.env" ]; then
    return 1
  fi

  # Load current settings
  source "${INSTALL_DIR}/.env"

  # Determine output type and command arguments
  local output_type="file"  # Default is file output
  local command_args="--output file --format csv --file /var/log/hems/data.csv"

  if [ -n "${WEBHOOK_URL}" ]; then
    output_type="webhook"  # Webhook output
    command_args="--output webhook"
  elif [ -n "${GCP_PROJECT_ID}" ] && [ -n "${GCP_TOPIC_NAME}" ]; then
    output_type="gcloud"  # Google Cloud Pub/Sub output
    command_args="--output gcloud"
  fi

  # 設定値を返す
  echo "${output_type},${WEBHOOK_URL:-},${GCP_PROJECT_ID:-},${GCP_TOPIC_NAME:-},${command_args}"
}

# Display service information
show_service_info() {
  echo "You can control the service with the following commands:"
  echo "  Start service:    sudo systemctl start ${SERVICE_NAME}"
  echo "  Stop service:     sudo systemctl stop ${SERVICE_NAME}"
  echo "  Service status:   sudo systemctl status ${SERVICE_NAME}"
  echo "  Enable autostart: sudo systemctl enable ${SERVICE_NAME}"
  echo "  Disable autostart: sudo systemctl disable ${SERVICE_NAME}"

  echo ""
  echo "Settings can be changed in the ${INSTALL_DIR}/.env file."
  echo "To change output settings, run the update command for interactive configuration."
  echo "sudo $0 update"
  echo ""
  echo "Start service: sudo systemctl start ${SERVICE_NAME}"
  echo "Enable autostart: sudo systemctl enable ${SERVICE_NAME}"
}
