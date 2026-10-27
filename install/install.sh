#!/usr/bin/env bash
# kde-stt installer — KDE Plasma 6 edition
# Run:  ./install/install.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="$HOME/.config/autostart"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
step() { bold "==> $1"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$1"; }

step "Building the project (uv sync)"
( cd "$PROJECT_DIR" && uv sync )

mkdir -p "$BIN_DIR" "$AUTOSTART_DIR" "$SYSTEMD_USER_DIR"

# --------------------------------------------------------------- 1. ydotoold

step "Setting up ydotoold (Wayland text injection)"

if [ ! -e /dev/uinput ]; then
    warn "kernel does not expose /dev/uinput — ydotool will not work."
fi

if ! id -nG "$USER" | grep -qw input; then
    warn "adding you to the 'input' group (needed for uinput access)"
    sudo usermod -aG input "$USER"
    warn "you must log out and back in for this to take effect"
fi

if [ ! -f /etc/udev/rules.d/80-uinput.rules ]; then
    warn "installing udev rule for uinput (requires sudo)"
    sudo tee /etc/udev/rules.d/80-uinput.rules >/dev/null <<'EOF'
KERNEL=="uinput", MODE="0660", GROUP="input"
EOF
    sudo udevadm control --reload-rules
fi

if [ ! -f "$SYSTEMD_USER_DIR/ydotoold.service" ]; then
    cat > "$SYSTEMD_USER_DIR/ydotoold.service" <<'EOF'
[Unit]
Description=ydotoold - ydotool daemon for Wayland text injection

[Service]
ExecStart=/usr/bin/ydotoold
Restart=on-failure

[Install]
WantedBy=graphical-session.target
EOF
fi

systemctl --user daemon-reload
systemctl --user enable --now ydotoold.service 2>/dev/null || true

# --------------------------------------------------------- 2. CLI entrypoints

step "Installing commands to $BIN_DIR"
for cmd in kde-stt kde-sttd kde-stt-frontend; do
    ln -sf "$PROJECT_DIR/.venv/bin/$cmd" "$BIN_DIR/$cmd"
done

# ------------------------------------------------------------- 3. autostart

step "Creating autostart entries"
cat > "$AUTOSTART_DIR/kde-sttd.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=kde-stt daemon
Exec=$BIN_DIR/kde-sttd
X-KDE-autostart-phase=2
EOF

cat > "$AUTOSTART_DIR/kde-stt-frontend.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=kde-stt overlay
Exec=$BIN_DIR/kde-stt-frontend
X-KDE-autostart-phase=2
EOF

# ------------------------------------------------------------- 4. KWin rules

step "Adding KWin window rule (keep overlay above everything)"
# The overlay window is frameless, so KWin identifies it by resource name.
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key description "kde-stt overlay"
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key windowresource "kde-stt-frontend"
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key windowresource-type "0"
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key above true
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key abovetype 1
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key skippager true
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key skippagertype 1
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key skiptaskbar true
kwriteconfig6 --file kwinrulesrc \
    --group 1 --key skiptaskbarmode true
if command -v qdbus6 >/dev/null 2>&1; then
    qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null || true
elif command -v qdbus >/dev/null 2>&1; then
    qdbus org.kde.KWin /KWin reconfigure 2>/dev/null || true
fi

# --------------------------------------------------------------- 5. summary

bold ""
bold "Installed. One manual step remains — binding the shortcut:"
echo ""
echo "  System Settings → Keyboard → Shortcuts → Add New → Custom Shortcut"
echo ""
echo "  1. Trigger:      Meta+Space (or your favorite key)"
echo "  2. Action:       Command/URL → kde-stt toggle"
echo ""
echo "  For push-to-talk instead, bind two triggers:"
echo "    press  → kde-stt start"
echo "    release → kde-stt stop"
echo ""
echo "Then start the daemon:"
echo "  $BIN_DIR/kde-sttd &"
echo "  $BIN_DIR/kde-stt-frontend &"
echo ""
echo "Test:  kde-stt status && kde-stt toggle"
