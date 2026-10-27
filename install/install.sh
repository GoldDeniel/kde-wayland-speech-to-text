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
    warn "you are not in the 'input' group (needed for uinput access)"
    if sudo -n true 2>/dev/null; then
        sudo usermod -aG input "$USER"
        warn "you must log out and back in for this to take effect"
    else
        warn "run this yourself (then log out and back in):"
        warn "    sudo usermod -aG input $USER"
        warn "    sudo tee /etc/udev/rules.d/80-uinput.rules <<< 'KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"'"
    fi
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

step "Creating autostart entries (logging to ~/.local/state/kde-stt/)"
LOG_DIR="$HOME/.local/state/kde-stt"
mkdir -p "$LOG_DIR"
cat > "$AUTOSTART_DIR/kde-sttd.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=kde-stt daemon
Exec=/bin/sh -c 'exec $BIN_DIR/kde-sttd >>$LOG_DIR/daemon.log 2>&1'
X-KDE-autostart-phase=2
EOF

cat > "$AUTOSTART_DIR/kde-stt-frontend.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=kde-stt overlay
Exec=/bin/sh -c 'exec $BIN_DIR/kde-stt-frontend >>$LOG_DIR/frontend.log 2>&1'
X-KDE-autostart-phase=2
EOF

# ------------------------------------------------------------- 4. KWin rules

step "Adding KWin window rule (always above, never takes focus)"
# KWin rule keys (from kwin's rules.cpp):
#   wmclass + wmclassmatch=1 (exact match)  -> match the app's resource class
#   above=true, aboverule=2 (Force)         -> keep above other windows
#   acceptfocus=false, acceptfocusrule=2    -> never steal focus, so the
#                                              Ctrl+V paste lands in the
#                                              window you were typing in.
RULE_GROUP="kde-stt-overlay"
kwriteconfig6 --file kwinrulesrc --group General --key rules "$RULE_GROUP"
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key description "kde-stt overlay"
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key enabled true
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key wmclass "kde-stt-frontend"
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key wmclassmatch 1
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key wmclasscomplete false
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key title "kde-stt overlay"
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key titlematch 1
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key above true
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key aboverule 2
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skiptaskbar true
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skiptaskbarrule 2
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skippager true
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skippagerrule 2
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skipswitcher true
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key skipswitcherrule 2
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key acceptfocus false
kwriteconfig6 --file kwinrulesrc --group "$RULE_GROUP" --key acceptfocusrule 2
# Remove the stale rule from the previous install attempt (wrong keys).
python3 - <<'PYEOF'
import configparser, os
path = os.path.expanduser("~/.config/kwinrulesrc")
c = configparser.ConfigParser()
c.optionxform = str
c.read(path)
if c.remove_section("1"):
    with open(path, "w") as f:
        c.write(f)
    print("    removed stale rule group '1'")
PYEOF
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
echo "  For hold-to-talk (push) mode instead, see README.md — it needs the"
echo "  daemon to watch the key via evdev (sudo usermod -aG input \"$USER\")."
echo ""
echo "Then start the daemon:"
echo "  $BIN_DIR/kde-sttd &"
echo "  $BIN_DIR/kde-stt-frontend &"
echo ""
echo "Test:  kde-stt status && kde-stt toggle"
