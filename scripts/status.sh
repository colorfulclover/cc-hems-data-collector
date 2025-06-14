#!/bin/bash

# HEMS Data Collector Status Check

# Load common utilities
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SOURCE_DIR}/common.sh"

# Status check function
check_status() {
  initialize
  systemctl status "${SERVICE_NAME}"
}

# Execute only if the script is directly run
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  check_status
fi
