#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.1"
BASE_URL="https://storage.googleapis.com/smartloop-gcp-us-east-releases/${VERSION}"
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/smartloop"

# Colors
MUTED='\033[0;2m'
PINK='\033[38;5;205m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# Expected sha256 checksums
DARWIN_ARM64_SHA256="7f0bcb1e9a28dd6fab7a92456ba7314a1bf594ead7a0bd084ea9fc42dba7d18a"
LINUX_AMD64_SHA256="3cc9c7b0f45dfd2c26b5fe7655abba48d924bfb0f1ab1baad57e34adedac1c70"

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }

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
}

print_progress() {
    local bytes="$1"
    local length="$2"
    [ "$length" -gt 0 ] || return 0

    local width=50
    local percent=$(( bytes * 100 / length ))
    [ "$percent" -gt 100 ] && percent=100
    local on=$(( percent * width / 100 ))
    local off=$(( width - on ))

    local filled=$(printf "%*s" "$on" "")
    filled=${filled// /■}
    local empty=$(printf "%*s" "$off" "")
    empty=${empty// /･}

    printf "\r${PINK}%s%s %3d%%${NC}" "$filled" "$empty" "$percent"
}

download_with_progress() {
    local url="$1"
    local output="$2"
    local length=0
    local bytes=0

    # Get content length
    length=$(curl -sI -L "$url" | grep -i content-length | tail -1 | awk '{print $2}' | tr -d '\r')
    length=${length:-0}

    if [ "$length" -gt 0 ] && [ -t 2 ]; then
        curl -sL "$url" -o "$output" --write-out "" 2>/dev/null &
        local curl_pid=$!

        while kill -0 "$curl_pid" 2>/dev/null; do
            if [ -f "$output" ]; then
                bytes=$(wc -c < "$output" 2>/dev/null | tr -d ' ')
                bytes=${bytes:-0}
                print_progress "$bytes" "$length"
            fi
            sleep 0.1
        done
        wait "$curl_pid"
        local ret=$?
        print_progress "$length" "$length"
        echo ""
        return $ret
    else
        curl -fL --progress-bar "$url" -o "$output"
    fi
}

add_to_path() {
    local config_file="$1"
    local command="export PATH=${INSTALL_DIR}:\$PATH"

    if grep -Fq "$INSTALL_DIR" "$config_file" 2>/dev/null; then
        return 0
    elif [[ -w "$config_file" ]]; then
        echo -e "\n# smartloop" >> "$config_file"
        echo "$command" >> "$config_file"
        echo -e "${MUTED}Successfully added ${NC}slp${MUTED} to \$PATH in ${NC}${config_file}"
    fi
}

setup_path() {
    if [[ ":$PATH:" == *":${INSTALL_DIR}:"* ]]; then
        return 0
    fi

    local found=false

    # Add to all existing shell config files
    for f in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.zshrc" "${ZDOTDIR:-$HOME}/.zshrc"; do
        if [[ -f "$f" ]]; then
            add_to_path "$f"
            found=true
        fi
    done

    # Handle fish separately
    local fish_config="$HOME/.config/fish/config.fish"
    if [[ -f "$fish_config" ]]; then
        if ! grep -Fq "$INSTALL_DIR" "$fish_config" 2>/dev/null; then
            echo -e "\n# smartloop" >> "$fish_config"
            echo "fish_add_path $INSTALL_DIR" >> "$fish_config"
            echo -e "${MUTED}Successfully added ${NC}slp${MUTED} to \$PATH in ${NC}${fish_config}"
        fi
        found=true
    fi

    if [[ "$found" == false ]]; then
        echo -e "${MUTED}Manually add to your shell config:${NC}"
        echo -e "  export PATH=${INSTALL_DIR}:\$PATH"
    fi
}

print_banner() {
    echo -e ""
    echo -e "${PINK}█▀ █▀▄▀█ ▄▀█ █▀█ ▀█▀ █   █▀█ █▀█ █▀█${NC}"
    echo -e "${PINK}▄█ █ ▀ █ █▀█ █▀▄  █  █▄▄ █▄█ █▄█ █▀▀${NC}"
    echo -e ""
    echo -e "${MUTED}Version: ${NC}${VERSION}"
    echo -e ""
    echo -e "${MUTED}To get started:${NC}"
    echo -e ""
    echo -e "  slp  ${MUTED}# Start the TUI${NC}"
    echo -e ""
    echo -e "${MUTED}For more information visit ${NC}https://smartloop.ai/docs/intro/"
    echo -e ""
}

install_smartloop() {
    local tmpdir archive_url expected_sha256

    detect_platform

    archive_url="${BASE_URL}/${OS}/${ARCH}/slp.tar.gz"
    expected_sha256="$(get_expected_sha256)"

    tmpdir="$(mktemp -d)"
    trap 'rm -rf "${tmpdir:-}"' EXIT

    echo -e "\n${MUTED}Downloading ${NC}smartloop${MUTED} version: ${NC}${VERSION}"
    download_with_progress "$archive_url" "${tmpdir}/slp.tar.gz"

    echo -e "${MUTED}Verifying checksum...${NC}"
    verify_checksum "${tmpdir}/slp.tar.gz" "$expected_sha256"

    echo -e "${MUTED}Extracting...${NC}"
    tar -xzf "${tmpdir}/slp.tar.gz" -C "$tmpdir"

    echo -e "${MUTED}Installing to ${NC}${INSTALL_DIR}${MUTED}...${NC}"
    mkdir -p "$LIB_DIR" "$INSTALL_DIR"
    rm -rf "${LIB_DIR:?}/"*
    cp -r "${tmpdir}/slp/"* "$LIB_DIR/"
    ln -sf "${LIB_DIR}/slp" "${INSTALL_DIR}/slp"

    create_path_shim

    echo -e "${MUTED}Verifying installation...${NC}"
    if ! "${INSTALL_DIR}/slp" --help &>/dev/null; then
        error "Installation verification failed: 'slp --help' did not succeed"
    fi

    setup_path

    echo -e "${MUTED}Starting background service...${NC}"
    if [ "$OS" = "linux" ]; then
        setup_systemd_service
    elif [ "$OS" = "darwin" ]; then
        setup_launchd_service
    fi

    print_banner
}

create_path_shim() {
    local shim_path=""
    
    if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
        shim_path="/usr/local/bin/slp"
    elif [ -w "/usr/bin" ]; then
        shim_path="/usr/bin/slp"
    fi

    if [ -n "$shim_path" ]; then
        if [ -L "$shim_path" ]; then
            rm -f "$shim_path"
        fi
        ln -sf "${LIB_DIR}/slp" "$shim_path"
        echo -e "${MUTED}Created shim at ${NC}${shim_path}${MUTED} (already in PATH)"
        return 0
    fi

    for dir in /usr/bin /usr/local/bin; do
        if [ ! -w "$(dirname "$dir")" ]; then
            continue
        fi
        if mkdir -p "$dir" 2>/dev/null && touch "$dir/slp_test" 2>/dev/null; then
            rm -f "$dir/slp_test"
            ln -sf "${LIB_DIR}/slp" "$dir/slp"
            echo -e "${MUTED}Created shim at ${NC}${dir}/slp${MUTED} (already in PATH)"
            return 0
        fi
    done

    echo -e "${MUTED}Could not create shim in system PATH. Using ${NC}${INSTALL_DIR}"
    echo -e "${MUTED}Note: You may need to restart your shell or run:${NC}"
    echo -e "  source ~/.bashrc  # or ~/.zshrc"
}

setup_launchd_service() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist="${plist_dir}/com.smartloop.server.plist"
    local log_dir="$HOME/Library/Logs"
    local log_file="${log_dir}/smartloop.log"

    # Remove legacy system-level daemon if present
    local legacy_plist="/Library/LaunchDaemons/com.smartloop.server.plist"
    if [ -f "$legacy_plist" ]; then
        sudo launchctl unload "$legacy_plist" 2>/dev/null || true
        sudo rm -f "$legacy_plist"
    fi

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

    if ! launchctl list com.smartloop.server 2>/dev/null | grep -q '"PID"'; then
        echo -e "${RED}Service failed to start.${NC} Check logs with: tail -50 ${log_file}"
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
        sudo systemctl stop smartloop 2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$legacy_service"
        sudo systemctl daemon-reload
    fi

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

    if ! systemctl --user is-active --quiet smartloop; then
        echo -e "${RED}Service failed to start.${NC} Check logs with: journalctl --user -u smartloop -n 50"
    fi
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    install_smartloop
fi
