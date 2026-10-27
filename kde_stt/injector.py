"""Text injection backends.

The daemon is desktop-agnostic; this module picks the right strategy:

- ydotool  : Wayland (KDE, GNOME) — uinput virtual device, needs ydotoold
- xdotool  : X11
- clipboard: fallback (wl-copy/xclip + paste shortcut)

Two injection modes:
  paste — fastest and most reliable (clipboard + Ctrl+V); restores the old
          clipboard content afterwards when possible.
  type  — simulates key-by-key typing; slower but leaves the clipboard alone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

from .config import InjectorConfig


class InjectionError(RuntimeError):
    pass


class Injector:
    def __init__(self, cfg: InjectorConfig):
        self.cfg = cfg
        self._backend = self._pick_backend()

    # ------------------------------------------------------------------ public

    def inject(self, text: str) -> None:
        if not text:
            return
        if self.cfg.mode == "type":
            self._backend.type_text(text)
        else:
            self._backend.paste(text, restore=self.cfg.restore_clipboard)

    def describe(self) -> str:
        return f"{self._backend.name} ({self.cfg.mode})"

    # ----------------------------------------------------------------- private

    def _pick_backend(self) -> "BaseBackend":
        session = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
        if session == "wayland" and shutil.which("ydotool") and _ydotoold_alive():
            return YdotoolBackend()
        if session == "x11" and shutil.which("xdotool"):
            return XdotoolBackend()
        if shutil.which("wl-copy") or shutil.which("xclip"):
            return ClipboardBackend()
        raise InjectionError(
            "no injection backend found: install ydotool (Wayland) or xdotool (X11)"
        )


class BaseBackend:
    name: str = "base"

    def type_text(self, text: str) -> None: ...
    def paste(self, text: str, *, restore: bool = True) -> None: ...


def _run(argv: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(argv, timeout=timeout, capture_output=True, text=True)


def _clipboard_set(text: str) -> bool:
    if shutil.which("wl-copy"):
        return _run(["wl-copy", text]).returncode == 0
    if shutil.which("xclip"):
        return _run(["xclip", "-selection", "clipboard", text]).returncode == 0
    return False


def _clipboard_get() -> str | None:
    if shutil.which("wl-paste"):
        proc = _run(["wl-paste"], timeout=1.0)
        return proc.stdout if proc.returncode == 0 else None
    if shutil.which("xclip"):
        proc = _run(["xclip", "-selection", "clipboard", "-o"], timeout=1.0)
        return proc.stdout if proc.returncode == 0 else None
    return None


def _paste_keypress() -> None:
    time.sleep(0.05)  # let the clipboard manager sync
    if shutil.which("ydotool"):
        _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])  # ctrl+v
    elif shutil.which("xdotool"):
        _run(["xdotool", "key", "ctrl+v"])


class YdotoolBackend(BaseBackend):
    name = "ydotool"

    def type_text(self, text: str) -> None:
        proc = _run(["ydotool", "type", "--key-delay", "8", "--", text])
        if proc.returncode != 0:
            raise InjectionError(f"ydotool type failed: {proc.stderr.strip()}")

    def paste(self, text: str, *, restore: bool = True) -> None:
        previous = _clipboard_get() if restore else None
        if not _clipboard_set(text):
            raise InjectionError("could not set the clipboard")
        _paste_keypress()
        if restore and previous is not None:
            _clipboard_set(previous)


class XdotoolBackend(BaseBackend):
    name = "xdotool"

    def type_text(self, text: str) -> None:
        _run(["xdotool", "type", "--delay", "8", "--", text])

    def paste(self, text: str, *, restore: bool = True) -> None:
        previous = _clipboard_get() if restore else None
        if not _clipboard_set(text):
            raise InjectionError("could not set the clipboard")
        _paste_keypress()
        if restore and previous is not None:
            _clipboard_set(previous)


class ClipboardBackend(BaseBackend):
    """Last resort: clipboard + paste shortcut only."""

    name = "clipboard"

    def type_text(self, text: str) -> None:
        self.paste(text, restore=False)

    def paste(self, text: str, *, restore: bool = True) -> None:
        previous = _clipboard_get() if restore else None
        if not _clipboard_set(text):
            raise InjectionError("could not set the clipboard")
        _paste_keypress()
        if restore and previous is not None:
            _clipboard_set(previous)


def _ydotoold_alive() -> bool:
    proc = _run(["pgrep", "-x", "ydotoold"], timeout=1.0)
    return proc.returncode == 0
