#!/bin/bash

# HEMS Data Collector Service Management Script
set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Commands and descriptions
COMMANDS=(
  "install:   Install the service"
  "update:    Update the service"
  "uninstall: Uninstall the service"
  "status:    Display service status"
)

# Display help
show_help() {
  echo "Usage: $0 <command>"
  echo ""
  echo "Available commands:"
  for cmd in "${COMMANDS[@]}"; do
    echo "  $cmd"
  done
}

# Check for root privileges before execution
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run with root privileges."
  echo "Please run: sudo ${0} $1"
  exit 1
fi

# Main process - call corresponding scripts
case "$1" in
  install)
    ${SCRIPT_DIR}/scripts/install.sh
    ;;
  update)
    ${SCRIPT_DIR}/scripts/update.sh
    ;;
  uninstall)
    ${SCRIPT_DIR}/scripts/uninstall.sh
    ;;
  status)
    ${SCRIPT_DIR}/scripts/status.sh
    ;;
  *)
    show_help
    exit 1
    ;;
esac

exit 0
