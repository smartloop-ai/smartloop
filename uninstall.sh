#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/usr/local/bin"
LIB_DIR="/usr/local/lib/smartloop"
SERVICE_FILE="/etc/systemd/system/smartloop.service"
LAUNCHD_PLIST="/Library/LaunchDaemons/com.smartloop.server.plist"
LOG_FILE="/var/log/smartloop.log"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$1"; }
error() { printf "\033[1;31mError:\033[0m %s\n" "$1" >&2; exit 1; }

uninstall_smartloop() {
    # Stop and disable systemd service (Linux)
    if [ -f "$SERVICE_FILE" ]; then
        info "Stopping and disabling smartloop service..."
        sudo systemctl stop smartloop   2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload
        info "Systemd service removed"
    fi

    # Unload launchd service (macOS)
    if [ -f "$LAUNCHD_PLIST" ]; then
        info "Unloading smartloop launchd service..."
        sudo launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
        sudo rm -f "$LAUNCHD_PLIST"
        info "Launchd service removed"
    fi

    # Remove symlink
    if [ -L "${INSTALL_DIR}/slp" ]; then
        info "Removing ${INSTALL_DIR}/slp..."
        sudo rm -f "${INSTALL_DIR}/slp"
    fi

    # Remove library directory
    if [ -d "$LIB_DIR" ]; then
        info "Removing ${LIB_DIR}..."
        sudo rm -rf "$LIB_DIR"
    fi

    # Remove log file
    if [ -f "$LOG_FILE" ]; then
        info "Removing log file ${LOG_FILE}..."
        sudo rm -f "$LOG_FILE"
    fi

    printf "\n\033[1;32mSmartloop uninstalled successfully.\033[0m\n"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    uninstall_smartloop
fi
