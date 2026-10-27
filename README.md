# KDE-STT

Press a global shortcut → a small animated dot appears → speak → your words are typed
into whatever window has focus. That's it.

Powered by **faster-whisper** (CTranslate2), **PipeWire** audio, and **ydotool** for
Wayland text injection. The whisper model stays loaded in RAM, so after the first
utterance transcription is near-instant.

## Architecture

```
┌───────────────────────────── session bus (D-Bus) ─────────────────────────────┐
│                                                                              │
│  ┌──────────────────┐        ┌──────────────────────────┐                    │
│  │  kde-sttd (core) │◄───────►│  kde-stt-frontend (UI)   │                    │
│  │  - recording     │ signals │  - Qt Quick overlay      │                    │
│  │  - transcription │  state  │  - animated dot, KDE/    │                    │
│  │  - text injection│         │    Plasma style          │                    │
│  └──────────────────┘         └──────────────────────────┘                    │
│         ▲                                                                     │
│         │ dbus client                                                         │
│  ┌──────┴──────┐                                                              │
│  │  kde-stt    │◄──── global shortcut (KDE "Custom Shortcuts")                │
│  │  (CLI)      │                                                              │
│  └─────────────┘                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
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

### Bind the shortcut (manual, one time)

**System Settings → Keyboard → Shortcuts → Add New → Custom Shortcut**

- Trigger: your key (e.g. `Meta+Space`), Activation: `Command/URL`
- Command: `kde-stt toggle`

For push-to-talk mode create two shortcuts instead:

- Trigger: `Meta+Space` press → command `kde-stt start`
- Trigger: `Meta+Space` release → command `kde-stt stop`

Press/release triggers are supported by the KDE "Custom Shortcuts" module
(set Trigger → Keyboard Shortcut → Gesture: Shortcuts → "press/release" style
is configured under the trigger's settings).

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

`~/.config/kde-stt/config.toml` (copy of `config.example.toml`):

```toml
[transcriber]
model = "small"          # tiny | base | small | medium | large-v3
device = "auto"          # auto | cpu | cuda
compute_type = "auto"    # auto | int8 | float16 | float32
language = "auto"        # auto-detect, or "en", "pl", ...
beam_size = 5

[injector]
mode = "paste"           # paste (clipboard+Ctrl+V, fast) | type (key-by-key)
```

## Notes / known trade-offs

- The overlay is a normal Qt window; on Wayland an app can't force itself above
  other windows, so the install script creates a KWin window rule instead.
- The GNOME Shell extension is planned as a separate frontend module; the
  daemon, CLI, and config all work unchanged.
- `ydotool` types through a virtual input device — some apps (e.g. Flatpaks with
  heavy input filtering) may behave differently; the clipboard-paste mode is the
  most reliable.
