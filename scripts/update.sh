#!/bin/bash

# HEMS Data Collector Update Process

# Load common utilities
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SOURCE_DIR}/common.sh"

# Update function
update_service() {
  initialize

  if ! id -u hems-data-collector &>/dev/null; then
    echo "Error: hems-data-collector user does not exist."
    echo "Please run installation first: $0 install"
    exit 1
  fi

  # Check if service is running
  service_was_active=false
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    service_was_active=true
    echo "Stopping service..."
    systemctl stop "${SERVICE_NAME}"
  fi

  # Update application directory
  echo "Updating application..."
  cp -a "${PROJECT_DIR}"/. "${INSTALL_DIR}"/
  chown -R hems-data-collector:hems-data-collector "${INSTALL_DIR}"

  # Check if output settings should be changed
  read -p "Do you want to change output settings? [y/N]: " change_output
  if [[ "$change_output" =~ ^[Yy]$ ]]; then
    # Backup existing settings
    cp "${INSTALL_DIR}/.env" "${INSTALL_DIR}/.env.bak"

    # Update settings
    update_settings
    if [ $? -eq 0 ]; then
      # サービスファイル再生成
      generate_service_file "$UPDATED_OUTPUT_TYPE" "$UPDATED_FILE_FORMAT"
    fi
  fi

  # Update dependencies
  echo "Updating dependency packages..."
  sudo -u hems-data-collector "${INSTALL_DIR}/venv/bin/pip" install -U -e "${INSTALL_DIR}"

  # Check if Google Cloud Pub/Sub dependencies are installed
  if sudo -u hems-data-collector "${INSTALL_DIR}/venv/bin/pip" freeze | grep -q google-cloud-pubsub; then
    echo "Updating Google Cloud Pub/Sub dependency packages..."
    sudo -u hems-data-collector "${INSTALL_DIR}/venv/bin/pip" install -U -e '"${INSTALL_DIR}"[gcloud]'
  fi

  # Regenerate service file (even if no changes)
  # generate_service_file

  # Reload systemd
  systemctl daemon-reload

  # Restart service (only if it was active before)
  if [ "$service_was_active" = true ]; then
    echo "Restarting service..."
    systemctl start "${SERVICE_NAME}"
  fi

  echo "${SERVICE_NAME} service update completed"
}

# Execute only if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  update_service
fi
