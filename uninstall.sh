#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/smartloop"
LEGACY_INSTALL_DIR="/usr/local/bin"
LEGACY_LIB_DIR="/usr/local/lib/smartloop"
SERVICE_FILE="$HOME/.config/systemd/user/smartloop.service"
LEGACY_SERVICE_FILE="/etc/systemd/system/smartloop.service"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/com.smartloop.server.plist"
LEGACY_LAUNCHD_PLIST="/Library/LaunchDaemons/com.smartloop.server.plist"
LOG_FILE="$HOME/Library/Logs/smartloop.log"
LEGACY_LOG_FILE="/var/log/smartloop.log"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$1"; }
error() { printf "\033[1;31mError:\033[0m %s\n" "$1" >&2; exit 1; }

uninstall_smartloop() {
    # Stop and disable systemd user service (Linux)
    if [ -f "$SERVICE_FILE" ]; then
        info "Stopping and disabling smartloop user service..."
        systemctl --user stop smartloop   2>/dev/null || true
        systemctl --user disable smartloop 2>/dev/null || true
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload
        info "Systemd user service removed"
    fi

    # Remove legacy system-level systemd service if present (Linux)
    if [ -f "$LEGACY_SERVICE_FILE" ]; then
        info "Removing legacy system service..."
        sudo systemctl stop smartloop 2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$LEGACY_SERVICE_FILE"
        sudo systemctl daemon-reload
        info "Legacy systemd service removed"
    fi

    # Unload launchd user agent (macOS)
    if [ -f "$LAUNCHD_PLIST" ]; then
        info "Unloading smartloop launchd user agent..."
        launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
        rm -f "$LAUNCHD_PLIST"
        info "Launchd user agent removed"
    fi

    # Remove legacy system daemon if present (macOS)
    if [ -f "$LEGACY_LAUNCHD_PLIST" ]; then
        info "Removing legacy system daemon..."
        sudo launchctl unload "$LEGACY_LAUNCHD_PLIST" 2>/dev/null || true
        sudo rm -f "$LEGACY_LAUNCHD_PLIST"
        info "Legacy launchd daemon removed"
    fi

    # Remove symlink
    if [ -L "${INSTALL_DIR}/slp" ]; then
        info "Removing ${INSTALL_DIR}/slp..."
        rm -f "${INSTALL_DIR}/slp"
    fi

    # Remove legacy symlink
    if [ -L "${LEGACY_INSTALL_DIR}/slp" ]; then
        info "Removing legacy ${LEGACY_INSTALL_DIR}/slp..."
        sudo rm -f "${LEGACY_INSTALL_DIR}/slp"
    fi

    # Remove library directory
    if [ -d "$LIB_DIR" ]; then
        info "Removing ${LIB_DIR}..."
        rm -rf "$LIB_DIR"
    fi

    # Remove legacy library directory
    if [ -d "$LEGACY_LIB_DIR" ]; then
        info "Removing legacy ${LEGACY_LIB_DIR}..."
        sudo rm -rf "$LEGACY_LIB_DIR"
    fi

    # Remove log files
    if [ -f "$LOG_FILE" ]; then
        info "Removing log file ${LOG_FILE}..."
        rm -f "$LOG_FILE"
    fi
    if [ -f "$LEGACY_LOG_FILE" ]; then
        info "Removing legacy log file ${LEGACY_LOG_FILE}..."
        sudo rm -f "$LEGACY_LOG_FILE"
    fi

    printf "\n\033[1;32mSmartloop uninstalled successfully.\033[0m\n"
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    uninstall_smartloop
fi
