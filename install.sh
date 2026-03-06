#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.1"
BASE_URL="https://storage.googleapis.com/smartloop-gcp-us-east-releases/${VERSION}"
INSTALL_DIR="$HOME/.smartloop"

# Colors
MUTED='\033[0;2m'
PINK='\033[38;5;205m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# Expected sha256 checksums
DARWIN_ARM64_SHA256="f83a5035c33e34a94ce90a16734fc69f07738ba9f3c83c4ee83441221fd07438"
LINUX_AMD64_SHA256="98101e4bfc34cbb70fe771c9cea3ac12e0cb09d90a42755747296c595a98200e"

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
    local command="$2"

    if grep -Fxq "$command" "$config_file" 2>/dev/null; then
        return 0
    fi

    if [[ -f "$config_file" ]] && [[ -w "$config_file" ]]; then
        echo -e "\n# smartloop" >> "$config_file"
        echo "$command" >> "$config_file"
        echo -e "${MUTED}Added ${NC}slp${MUTED} to \$PATH in ${NC}${config_file}"
    else
        echo -e "${MUTED}Manually add to ${NC}${config_file}${MUTED}:${NC}"
        echo -e "  $command"
    fi
}

setup_path() {
    # Make slp available in the current session immediately
    export PATH="${INSTALL_DIR}:$PATH"

    # Already on PATH (e.g. from a previous install), nothing to persist
    if [[ ":$PATH:" == *":$INSTALL_DIR:"* ]] && grep -Fq "$INSTALL_DIR" "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.config/fish/config.fish" 2>/dev/null; then
        return 0
    fi

    local current_shell config_files config_file path_command
    current_shell="$(basename "$SHELL")"

    case "$current_shell" in
        fish)
            config_files="$HOME/.config/fish/config.fish"
            path_command="fish_add_path $INSTALL_DIR"
            ;;
        zsh)
            config_files="${ZDOTDIR:-$HOME}/.zshrc"
            path_command="export PATH=\"${INSTALL_DIR}:\$PATH\""
            ;;
        bash)
            config_files="$HOME/.bashrc $HOME/.bash_profile $HOME/.profile"
            path_command="export PATH=\"${INSTALL_DIR}:\$PATH\""
            ;;
        *)
            config_files="$HOME/.bashrc $HOME/.profile"
            path_command="export PATH=\"${INSTALL_DIR}:\$PATH\""
            ;;
    esac

    # Find the first existing config file for the detected shell
    config_file=""
    for f in $config_files; do
        if [[ -f "$f" ]]; then
            config_file="$f"
            break
        fi
    done

    if [[ -z "$config_file" ]]; then
        echo -e "${MUTED}No config file found for ${NC}${current_shell}${MUTED}. Manually add to your shell config:${NC}"
        echo -e "  $path_command"
        return 0
    fi

    add_to_path "$config_file" "$path_command"
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
    echo -e "  slp status  ${MUTED}# Check if the server is running${NC}"
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
    mkdir -p "$INSTALL_DIR"
    rm -rf "${INSTALL_DIR:?}/"*
    cp -r "${tmpdir}/slp/"* "$INSTALL_DIR/"

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
    <string>${INSTALL_DIR}</string>
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
WorkingDirectory=${INSTALL_DIR}
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
