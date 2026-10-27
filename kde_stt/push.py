"""Push-to-talk: hold a physical key to talk, release to transcribe.

KDE global shortcuts (KGlobalAccel) only fire on key press — there is no
release event, so a true hold-to-talk cannot be done with a compositor
shortcut. Instead the daemon watches the key directly via evdev, which works
on any desktop environment (KDE, GNOME, sway, ...).

Requires read access to /dev/input/event* — i.e. membership of the 'input'
group:

    sudo usermod -aG input "$USER"   # then log out and back in

Configure in ~/.config/kde-stt/config.toml:

    [shortcut]
    mode = "push"
    push_key = "left-ctrl"   # evdev key name, lowercase, without KEY_ prefix
"""

from __future__ import annotations

import glob
import logging
import threading
from select import select

from evdev import InputDevice, ecodes

from .config import ShortcutConfig

log = logging.getLogger("kde-stt.push")

# Key names users can write in config.toml -> evdev KEY_* names.
KEY_ALIASES = {
    "left-ctrl": "KEY_LEFTCTRL",
    "right-ctrl": "KEY_RIGHTCTRL",
    "left-alt": "KEY_LEFTALT",
    "right-alt": "KEY_RIGHTALT",
    "left-shift": "KEY_LEFTSHIFT",
    "right-shift": "KEY_RIGHTSHIFT",
    "left-meta": "KEY_LEFTMETA",
    "right-meta": "KEY_RIGHTMETA",
    "capslock": "KEY_CAPSLOCK",
    "f9": "KEY_F9",
    "f10": "KEY_F10",
    "f11": "KEY_F11",
    "f12": "KEY_F12",
    "f13": "KEY_F13",
    "scrolllock": "KEY_SCROLLLOCK",
    "pause": "KEY_PAUSE",
    "insert": "KEY_INSERT",
    "home": "KEY_HOME",
    "end": "KEY_END",
    "pageup": "KEY_PAGEUP",
    "pagedown": "KEY_PAGEDOWN",
}


class PushToTalkWatcher:
    """Watches one key across all keyboard devices and calls back on press/release."""

    def __init__(self, cfg: ShortcutConfig, on_press, on_release):
        self.cfg = cfg
        self.on_press = on_press
        self.on_release = on_release
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> bool:
        try:
            key_code = resolve_key(self.cfg.push_key)
        except ValueError as exc:
            log.warning("push-to-talk disabled: %s", exc)
            return False
        devices = _find_devices()
        if not devices:
            log.warning(
                "push-to-talk disabled: no readable /dev/input/event* devices "
                "(add yourself to the 'input' group and log out and back in)"
            )
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(key_code, devices),
            daemon=True,
            name="kde-stt-push",
        )
        self._thread.start()
        log.info(
            "push-to-talk active: hold '%s' to talk (watching %d device(s))",
            self.cfg.push_key,
            len(devices),
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self, key_code: int, devices: list[InputDevice]) -> None:
        held = False
        try:
            while not self._stop.is_set():
                readable, _, _ = select(devices, [], [], 1.0)
                if not readable:
                    continue
                for device in readable:
                    for event in device.read():
                        if event.type != ecodes.EV_KEY or event.code != key_code:
                            continue
                        if event.value == 1 and not held:
                            held = True
                            self.on_press()
                        elif event.value == 0 and held:
                            held = False
                            self.on_release()
        except Exception:
            log.exception("push-to-talk watcher crashed")


def resolve_key(name: str) -> int:
    """'left-ctrl' -> ecodes.KEY_LEFTCTRL. Also accepts raw 'key_f9' style."""
    clean = name.strip().lower()
    if clean.startswith("key_"):
        key_name = clean.upper()
    else:
        key_name = KEY_ALIASES.get(clean) or f"KEY_{clean.upper()}"
    code = getattr(ecodes, key_name, None)
    if code is None:
        known = ", ".join(sorted(KEY_ALIASES))
        raise ValueError(
            f"unknown push_key '{name}'. Use one of the aliases ({known}) or "
            "an evdev key name like 'key_f9'."
        )
    return code


def _find_devices() -> list[InputDevice]:
    """Open every keyboard-like device we can read."""
    devices = []
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            dev = InputDevice(path)
            if "KEY_LEFTCTRL" in dev.capabilities().get(ecodes.EV_KEY, []):
                devices.append(dev)
        except (PermissionError, OSError):
            continue
    return devices
