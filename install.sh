#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.1"
BASE_URL="https://storage.googleapis.com/smartloop-gcp-us-east-releases/${VERSION}"
INSTALL_DIR="/usr/local/bin"
LIB_DIR="/usr/local/lib/smartloop"

# Expected sha256 checksums
DARWIN_ARM64_SHA256="cb6037023695a0340110c386fb4a03a453a15ae8ee41d199c3aff575819f4187"
LINUX_AMD64_SHA256="11070808f96dbc039b95dfd0d088b6b8bfe6c7997d5fce85af892339f285b4d4"

info() { printf "\033[1;34m==>\033[0m %s\n" "$1"; }
error() { printf "\033[1;31mError:\033[0m %s\n" "$1" >&2; exit 1; }

detect_platform() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Darwin) OS="darwin" ;;
        Linux)  OS="linux" ;;
        *)      error "Unsupported OS: $os" ;;
    esac

    case "$arch" in
        arm64|aarch64) ARCH="arm64" ;;
        x86_64)        ARCH="amd64" ;;
        *)             error "Unsupported architecture: $arch" ;;
    esac

    if [ "$OS" = "darwin" ] && [ "$ARCH" != "arm64" ]; then
        error "Only Apple Silicon (arm64) is supported on macOS"
    fi

    if [ "$OS" = "linux" ] && [ "$ARCH" != "amd64" ]; then
        error "Only x86_64 (amd64) is supported on Linux"
    fi
}

get_expected_sha256() {
    if [ "$OS" = "darwin" ] && [ "$ARCH" = "arm64" ]; then
        echo "$DARWIN_ARM64_SHA256"
    elif [ "$OS" = "linux" ] && [ "$ARCH" = "amd64" ]; then
        echo "$LINUX_AMD64_SHA256"
    fi
}

verify_checksum() {
    local file="$1" expected="$2" actual

    if command -v sha256sum &>/dev/null; then
        actual="$(sha256sum "$file" | awk '{print $1}')"
    elif command -v shasum &>/dev/null; then
        actual="$(shasum -a 256 "$file" | awk '{print $1}')"
    else
        error "No sha256 tool found (need sha256sum or shasum)"
    fi

    if [ "$actual" != "$expected" ]; then
        error "Checksum verification failed.\n  Expected: $expected\n  Got:      $actual"
    fi

    info "Checksum verified"
}

install_smartloop() {
    local tmpdir archive_url expected_sha256

    detect_platform
    info "Detected platform: ${OS}/${ARCH}"

    archive_url="${BASE_URL}/${OS}/${ARCH}/slp.tar.gz"
    expected_sha256="$(get_expected_sha256)"

    tmpdir="$(mktemp -d)"
    trap 'rm -rf "${tmpdir:-}"' EXIT

    info "Downloading Smartloop v${VERSION}..."
    curl -fL --progress-bar "$archive_url" -o "${tmpdir}/slp.tar.gz"

    info "Verifying checksum..."
    verify_checksum "${tmpdir}/slp.tar.gz" "$expected_sha256"

    info "Extracting..."
    tar -xzf "${tmpdir}/slp.tar.gz" -C "$tmpdir"

    info "Installing to ${LIB_DIR}..."
    sudo mkdir -p "$LIB_DIR" "$INSTALL_DIR"
    sudo rm -rf "${LIB_DIR:?}/"*
    sudo cp -r "${tmpdir}/slp/"* "$LIB_DIR/"
    sudo ln -sf "${LIB_DIR}/slp" "${INSTALL_DIR}/slp"

    info "Installed slp to ${INSTALL_DIR}/slp"

    info "Verifying installation..."
    if ! "${INSTALL_DIR}/slp" --help &>/dev/null; then
        error "Installation verification failed: 'slp --help' did not succeed"
    fi
    info "slp --help check passed"

    # Create service
    if [ "$OS" = "linux" ]; then
        setup_systemd_service
    elif [ "$OS" = "darwin" ]; then
        setup_launchd_service
    fi
}

setup_launchd_service() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist="${plist_dir}/com.smartloop.server.plist"
    local log_dir="$HOME/Library/Logs"
    local log_file="${log_dir}/smartloop.log"

    # Remove legacy system-level daemon if present
    local legacy_plist="/Library/LaunchDaemons/com.smartloop.server.plist"
    if [ -f "$legacy_plist" ]; then
        info "Removing legacy system daemon..."
        sudo launchctl unload "$legacy_plist" 2>/dev/null || true
        sudo rm -f "$legacy_plist"
    fi

    info "Creating launchd user agent..."

    mkdir -p "$plist_dir" "$log_dir"

    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartloop.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/slp</string>
        <string>server</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${LIB_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${log_file}</string>
    <key>StandardErrorPath</key>
    <string>${log_file}</string>
</dict>
</plist>
EOF

    launchctl unload "$plist" 2>/dev/null || true
    launchctl load -w "$plist"

    info "Launchd user agent created and loaded"

    if launchctl list com.smartloop.server 2>/dev/null | grep -q '"PID"'; then
        info "Service is running"
    else
        error "Service failed to start. Check logs with: tail -50 ${log_file}"
    fi
}

setup_systemd_service() {
    local service_dir="$HOME/.config/systemd/user"
    local service_file="${service_dir}/smartloop.service"
    local log_dir="$HOME/.local/log"
    local log_file="${log_dir}/smartloop.log"

    # Remove legacy system-level service if present
    local legacy_service="/etc/systemd/system/smartloop.service"
    if [ -f "$legacy_service" ]; then
        info "Removing legacy system service..."
        sudo systemctl stop smartloop 2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$legacy_service"
        sudo systemctl daemon-reload
    fi

    info "Creating systemd user service..."

    mkdir -p "$service_dir" "$log_dir"

    cat > "$service_file" <<EOF
[Unit]
Description=Smartloop Server
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/slp server start
Restart=on-failure
RestartSec=5
WorkingDirectory=${LIB_DIR}
StandardOutput=append:${log_file}
StandardError=append:${log_file}

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable smartloop
    systemctl --user restart smartloop

    # Enable lingering so the user service starts at boot without login
    loginctl enable-linger "$(whoami)" 2>/dev/null || true

    info "Systemd user service created, enabled, and started"

    if systemctl --user is-active --quiet smartloop; then
        info "Service is running"
    else
        error "Service failed to start. Check logs with: journalctl --user -u smartloop -n 50"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    install_smartloop
fi
