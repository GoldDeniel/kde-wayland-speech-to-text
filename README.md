# KDE-STT

Press a global shortcut → a small round assistant button appears → speak → your words are typed
into whatever window has focus. That's it.

Powered by **faster-whisper** (CTranslate2), **PipeWire** audio, and **ydotool** for
Wayland text injection. The whisper model stays loaded in RAM, so after the first
utterance transcription is near-instant.

## Architecture

```
┌───────────────────────────── session bus (D-Bus) ────────────────┐
│                                                                  │
│  ┌──────────────────┐        ┌──────────────────────────┐        │
│  │  kde-sttd (core) │◄───────►│  kde-stt-frontend (UI)   │       │
│  │  - recording     │ signals │  - Qt Quick overlay      │       │
│  │  - transcription │  state  │  - round AI button,      │       │
│  │  - text injection│         │    KDE/Plasma style      │       │
│  └──────────────────┘         └──────────────────────────┘       │
│         ▲                                                        │
│         │ dbus client                                            │
│  ┌──────┴──────┐                                                 │
│  │  kde-stt    │◄──── global shortcut (KDE "Custom Shortcuts")   │
│  │  (CLI)      │                                                 │
│  └─────────────┘                                                 │
└──────────────────────────────────────────────────────────────────┘
```

The core daemon is desktop-agnostic. Only the **frontend** and the **shortcut
registration** are desktop-specific — that's the modular part:

- `kde_stt/` — core daemon (recording, transcription, injection, D-Bus API)
- `kde_stt/frontend/` — Qt Quick overlay for KDE Plasma 6
- `plasmoid/` — future native Plasma applet (optional tray module)
- `install/` — setup scripts (daemon autostart, uinput permissions, KWin rules)

## Requirements

- Python 3.11+, `uv`
- PipeWire (PulseAudio compat) — standard on modern distros
- `ydotool` + `ydotoold` (Wayland) and/or `xdotool` (X11)
- `wl-copy` / `wl-paste` for clipboard (Wayland) or `xclip` (X11)

## Install

```bash
cd ~/Projects/KDE-STT
uv sync
./install/install.sh
```

The script:
1. sets up `ydotoold` (systemd user service) and grants `uinput` access,
2. creates autostart entries for the daemon + frontend,
3. adds a KWin window rule so the overlay stays above all windows,
4. prints the final manual step: binding the shortcut.

### Bind the shortcut (toggle mode — default)

**System Settings → Keyboard → Shortcuts → Add New → Custom Shortcut**

1. Trigger: your key (e.g. `Meta+Space`), Activation: `Command/URL`
2. Command: `kde-stt toggle`

Press to start, press again to stop and transcribe.

### Hold mode (push-to-talk)

KDE global shortcuts only fire on **press** — there is no release event, so
true hold-to-talk cannot be done with a compositor shortcut. Instead the
daemon watches the key directly via evdev, which works on any desktop.

1. Give the daemon access to raw key events (one time):

   ```bash
   sudo usermod -aG input "$USER"   # then log out and back in
   ```

2. Edit `~/.config/kde-stt/config.toml`:

   ```toml
   [shortcut]
   mode = "push"
   push_key = "left-ctrl"   # hold this key to talk; release = transcribe
   ```

3. Restart the daemon. No desktop shortcut is needed at all in push mode.

   `push_key` accepts aliases: `left-ctrl`, `right-ctrl`, `left-alt`,
   `right-alt`, `left-shift`, `right-shift`, `left-meta`, `right-meta`,
   `capslock`, `f9`…`f13`, `pause`, `insert`, `home`, `end`, `pageup`,
   `pagedown` — or any evdev name like `key_f13`.

   ⚠️ Pick a key you don't use for anything else; in push mode the key is
   consumed by the daemon while it's watching. `left-ctrl` alone will
   interfere with Ctrl+V, so `right-ctrl` or `capslock` are good choices.
   If holding the key does nothing, check the daemon log — it will say
   whether it could open the input devices.

You can also use both: `kde-stt toggle` via shortcut for toggle, and hold the
push key for push-to-talk (the daemon handles both simultaneously — the
shortcut just calls the same D-Bus methods).

## Usage

```bash
kde-stt toggle      # start/stop recording
kde-stt status      # daemon state, current model
kde-stt model small # switch model on the fly (tiny, base, small, medium, large-v3)
kde-stt start       # push-to-talk: begin
kde-stt stop        # push-to-talk: stop + transcribe
kde-stt cancel      # discard the current recording
```

## Configuration

`~/.config/kde-stt/config.toml` (see `config.example.toml` for a complete
example):

If you do not have one yet:

```bash
mkdir -p ~/.config/kde-stt
cp config.example.toml ~/.config/kde-stt/config.toml
```

```toml
[transcriber]
model = "small"          # tiny | base | small | medium | large-v3
device = "auto"          # auto | cpu | cuda
compute_type = "auto"    # auto | int8 | float16 | float32
language = "auto"        # auto-detect, or "en", "pl", ...
beam_size = 5

[injector]
mode = "paste"           # paste (clipboard+Ctrl+V, fast) | type (key-by-key)
restore_clipboard = false  # false = keep the transcribed text on the clipboard

[shortcut]
mode = "toggle"          # toggle | push (hold-to-talk, see README)
push_key = "left-ctrl"

[frontend]
position = "bottom-center"  # see the placement table below
size = 80                   # round button diameter in pixels (48-240)
margin = 64                 # gap from the screen edge in pixels
```

### Overlay placement and size

The `[frontend]` section controls where the round overlay button appears and
how large it is. `position` accepts these nine anchors:

| Value | Placement |
| --- | --- |
| `top-left` | top-left corner |
| `top-center` | top edge, horizontally centered |
| `top-right` | top-right corner |
| `middle-left` | left edge, vertically centered |
| `center` | exact middle of the screen |
| `middle-right` | right edge, vertically centered |
| `bottom-left` | bottom-left corner |
| `bottom-center` | bottom edge, horizontally centered |
| `bottom-right` | bottom-right corner |

- `size` is the diameter of the button in pixels. Default: `88` (allowed range
  `48`–`240`).
- `margin` is the gap between the button and the screen edge, in pixels.
  Default: `64`. It is only used for edge and corner positions.
- Shorthands `top`, `bottom`, `left`, `right`, and `middle` are also accepted.
- On KDE Wayland, the frontend loads a small KWin script at startup that moves
  the button to the configured anchor on the active screen. On X11, normal
  window coordinates are used. No manual KWin setup is required.
- Changes to `[frontend]` are picked up automatically the next time the overlay
  appears — no frontend restart is needed. The KWin positioning script is
  refreshed at the same time.
- Daemon-side settings (`[transcriber]`, `[injector]`, `[shortcut]`) are still
  read when `kde-sttd` starts; restart the daemon after changing those, or use
  `kde-stt model <name>` to switch models live.

## Debugging

The daemon and frontend log to `~/.local/state/kde-stt/` (installed via
autostart with log redirection). After a failed attempt:

```bash
tail -30 ~/.local/state/kde-stt/daemon.log
kde-stt status   # last_text shows what whisper actually heard
```

The log shows every pipeline step: `transcribed: '...' (language, ms)` →
`injecting N chars via <backend>` → `injection done` — or the exact error.

**Test injection without speaking:**

```bash
kde-stt inject "hello world"   # pastes into whatever window has focus
```

If that works but real recordings don't, check `last_text` in `kde-stt status`:
empty means whisper heard silence (wrong mic device — set `input_device` in
config.toml or check your PipeWire default source).

## Notes / known trade-offs

- The overlay is a normal Qt window; on Wayland an app can't force itself above
  other windows, so the install script creates a KWin window rule instead.
- The GNOME Shell extension is planned as a separate frontend module; the
  daemon, CLI, and config all work unchanged.
- `ydotool` types through a virtual input device — some apps (e.g. Flatpaks with
  heavy input filtering) may behave differently; the clipboard-paste mode is the
  most reliable.
