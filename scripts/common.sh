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
  local file_format="$2"
  local command_args=""

  # Set command arguments according to output type
  case "$output_type" in
    "webhook")
      command_args="--output webhook"
      ;;
    "gcloud")
      command_args="--output gcloud"
      ;;
    "file"|*) # Default to file output
      local format=${file_format:-csv}
      local log_file="/var/log/hems/data.${format}"
      command_args="--output file --format ${format} --file ${log_file}"
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

  UPDATED_OUTPUT_TYPE="${output_type}"
  UPDATED_FILE_FORMAT="${file_format}"
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
  local file_format="${10}"

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
    1)
      cat >> "${INSTALL_DIR}/.env" << EOF

# File output settings
FILE_FORMAT=${file_format}
EOF
      ;;
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
  generate_service_file "$output_type" "$file_format"
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
  echo -e "\nPlease select the data output destination:"
  echo "1) File output (default)"
  echo "2) Webhook"
  echo "3) Google Cloud Pub/Sub"
  read -p "Selection [1-3]: " output_choice
  output_choice=${output_choice:-1}

  # Initial settings (default: file output)
  webhook_url=""
  gcp_project_id=""
  gcp_topic_name=""
  file_format="csv"

  # Additional settings according to the selected output type
  case $output_choice in
    1)
      echo "File output selected."
      read -p "Select file format (csv/json) [csv]: " file_format_input
      file_format=${file_format_input:-csv}
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

  # Export settings to global variables
  SETTINGS_SERIAL_PORT="${serial_port}"
  SETTINGS_SERIAL_RATE="${serial_rate}"
  SETTINGS_B_ROUTE_ID="${b_route_id}"
  SETTINGS_B_ROUTE_PASSWORD="${b_route_password}"
  SETTINGS_OUTPUT_CHOICE="${output_choice}"
  SETTINGS_WEBHOOK_URL="${webhook_url}"
  SETTINGS_GCP_PROJECT_ID="${gcp_project_id}"
  SETTINGS_GCP_TOPIC_NAME="${gcp_topic_name}"
  SETTINGS_TIMEZONE="${timezone}"
  SETTINGS_FILE_FORMAT="${file_format}"
}

# Update settings
update_settings() {
  echo -e "\nPlease select the new data output destination:"
  echo "1) File output"
  echo "2) Webhook"
  echo "3) Google Cloud Pub/Sub"
  read -p "Selection [1-3]: " output_choice
  output_choice=${output_choice:-1}


  # Additional settings according to the selected output type
  local output_type
  local file_format

  # Clear old output-specific settings from .env file
  if [ -f "${INSTALL_DIR}/.env" ]; then
    sed -i -e '/^WEBHOOK_URL=/d' \
           -e '/^GCP_PROJECT_ID=/d' \
           -e '/^GCP_TOPIC_NAME=/d' \
           -e '/^FILE_FORMAT=/d' \
           "${INSTALL_DIR}/.env"
  fi

  case $output_choice in
    1)
      echo "File output selected."
      output_type="file"

      read -p "Select file format (csv/json) [csv]: " file_format_input
      file_format=${file_format_input:-csv}
      
      echo "FILE_FORMAT=${file_format}" >> "${INSTALL_DIR}/.env"
      ;;
    2)
      echo "Webhook output selected."
      output_type="webhook"
      file_format=""

      read -p "New Webhook URL: " webhook_url
      while [ -z "$webhook_url" ]; do
        echo "Webhook URL is required."
        read -p "New Webhook URL: " webhook_url
      done
      echo "WEBHOOK_URL=${webhook_url}" >> "${INSTALL_DIR}/.env"
      ;;
    3)
      echo "Google Cloud Pub/Sub output selected."
      output_type="gcloud"
      file_format=""

      read -p "New GCP Project ID: " gcp_project_id
      while [ -z "$gcp_project_id" ]; do
        echo "GCP Project ID is required."
        read -p "New GCP Project ID: " gcp_project_id
      done

      read -p "New Pub/Sub topic name: " gcp_topic_name
      while [ -z "$gcp_topic_name" ]; do
        echo "Pub/Sub topic name is required."
        read -p "New Pub/Sub topic name: " gcp_topic_name
      done
      
      echo "GCP_PROJECT_ID=${gcp_project_id}" >> "${INSTALL_DIR}/.env"
      echo "GCP_TOPIC_NAME=${gcp_topic_name}" >> "${INSTALL_DIR}/.env"
      ;;
    *)
      echo "Invalid selection. Defaulting to file output."
      output_type="file"
      file_format="csv"
      echo "FILE_FORMAT=csv" >> "${INSTALL_DIR}/.env"
      ;;
  esac

  UPDATED_OUTPUT_TYPE="${output_type}"
  UPDATED_FILE_FORMAT="${file_format}"
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

# Install service dependencies
install_dependencies() {
  # Implementation of install_dependencies function
  echo "Installing service dependencies..."
}
