#!/bin/bash

# HEMS Data Collector Installation Process

# Load common utilities
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SOURCE_DIR}/common.sh"

# Installation function
install_service() {
  initialize

  # Check if hems-data-collector user exists, create it if not
  if ! id -u hems-data-collector &>/dev/null; then
    echo "Creating hems-data-collector user..."
    useradd -r -s /bin/false -m -d "${INSTALL_DIR}" hems-data-collector
    usermod -aG dialout hems-data-collector
  fi

  # Create necessary directories
  mkdir -p "${DATA_DIR}"
  chown hems-data-collector:hems-data-collector "${DATA_DIR}"

  # Create application directory and copy source code
  if [ ! -d "${INSTALL_DIR}" ]; then
    echo "Installing application to ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    cp -a "${PROJECT_DIR}"/. "${INSTALL_DIR}"/
    chown -R hems-data-collector:hems-data-collector "${INSTALL_DIR}"
  else
    echo "Application directory already exists. Updating..."
    cp -a "${PROJECT_DIR}"/. "${INSTALL_DIR}"/
    chown -R hems-data-collector:hems-data-collector "${INSTALL_DIR}"
  fi

  # Python virtual environment setup
  if [ ! -d "${INSTALL_DIR}/venv" ]; then
    echo "Setting up Python virtual environment..."
    cd "${INSTALL_DIR}"
    python3 -m venv venv
    chown -R hems-data-collector:hems-data-collector "${INSTALL_DIR}/venv"

    # Install dependencies
    echo "Installing dependency packages..."
    sudo -u hems-data-collector "${INSTALL_DIR}/venv/bin/pip" install -e "${INSTALL_DIR}"

    # Check if Google Cloud Pub/Sub should be installed
    read -p "Do you want to install Google Cloud Pub/Sub functionality? [y/N]: " install_gcloud
    if [[ "$install_gcloud" =~ ^[Yy]$ ]]; then
      echo "Installing Google Cloud Pub/Sub dependency packages..."
      sudo -u hems-data-collector "${INSTALL_DIR}/venv/bin/pip" install -e '"${INSTALL_DIR}"[gcloud]'
    fi
  fi

  # Create environment variable settings file
  if [ ! -f "${INSTALL_DIR}/.env" ]; then
    echo "Creating environment variable settings file..."

    # Collect settings
    collect_settings

    # Create environment variables file
    create_env_file "$SETTINGS_SERIAL_PORT" "$SETTINGS_SERIAL_RATE" "$SETTINGS_B_ROUTE_ID" \
                   "$SETTINGS_B_ROUTE_PASSWORD" "$SETTINGS_OUTPUT_CHOICE" "$SETTINGS_WEBHOOK_URL" \
                   "$SETTINGS_GCP_PROJECT_ID" "$SETTINGS_GCP_TOPIC_NAME" "$SETTINGS_TIMEZONE"
  fi

  # Generate service file
  generate_service_file

  # Reload systemd
  systemctl daemon-reload

  echo "${SERVICE_NAME} service has been installed"
  show_service_info
}

# Execute only if the script is directly run
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_service
fi
