#!/bin/bash

# HEMS Data Collector Uninstallation Process

# Load common utilities
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SOURCE_DIR}/common.sh"

# Uninstallation function
uninstall_service() {
  initialize

  echo "Uninstalling ${SERVICE_NAME} service..."

  # Check if service is running and stop it
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "Stopping service..."
    systemctl stop "${SERVICE_NAME}"
  fi

  # Disable service
  if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "Disabling service autostart..."
    systemctl disable "${SERVICE_NAME}"
  fi

  # Remove service file
  if [ -f "${SERVICE_FILE}" ]; then
    echo "Removing service file..."
    rm "${SERVICE_FILE}"
    systemctl daemon-reload
  fi

  # Confirm removal of application and data directories
  read -p "Do you want to remove the application directory (${INSTALL_DIR})? [y/N]: " remove_app
  if [[ "$remove_app" =~ ^[Yy]$ ]]; then
    echo "Removing application directory..."
    rm -rf "${INSTALL_DIR}"
  fi

  read -p "Do you want to remove the data directory (${DATA_DIR})? [y/N]: " remove_data
  if [[ "$remove_data" =~ ^[Yy]$ ]]; then
    echo "Removing data directory..."
    rm -rf "${DATA_DIR}"
  fi

  # Confirm user removal
  read -p "Do you want to remove the ${SERVICE_NAME} user? [y/N]: " remove_user
  if [[ "$remove_user" =~ ^[Yy]$ ]]; then
    echo "Removing user..."
    userdel -r "${SERVICE_NAME}" 2>/dev/null || true
  fi

  echo "Uninstallation complete."
}

# Execute only if the script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  uninstall_service
fi
