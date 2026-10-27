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

import logging
import os
import shutil
import subprocess
import time

from .config import InjectorConfig

log = logging.getLogger("kde-stt.injector")


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
        log.info("injecting %d chars via %s", len(text), self.describe())
        # Always leave the final text on the clipboard — the user can paste it
        # again if the injection went somewhere unexpected.
        if self.cfg.mode == "type":
            self._backend.type_text(text)
            self._backend.copy_to_clipboard(text)
        else:
            self._backend.paste(text, restore=self.cfg.restore_clipboard)
        log.info("injection done")

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
    def copy_to_clipboard(self, text: str) -> None:
        if not _clipboard_set(text):
            raise InjectionError("could not set the clipboard")


def _run(argv: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(argv, timeout=timeout, capture_output=True, text=True)


def _clipboard_set(text: str) -> bool:
    # wl-copy (and xclip) fork a child that keeps serving the clipboard while
    # holding the inherited stdout/stderr pipes open. Capturing pipes therefore
    # blocks forever — discard the fds and wait only for the short-lived parent.
    if shutil.which("wl-copy"):
        proc = subprocess.run(
            ["wl-copy", text],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )
        return proc.returncode == 0
    if shutil.which("xclip"):
        proc = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            stdin=None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )
        return proc.returncode == 0
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
    # wl-copy sets the clipboard and stays alive to serve it; give the
    # compositor/clipboard manager a moment to see the new content.
    time.sleep(0.15)
    if shutil.which("ydotool"):
        proc = _run(["ydotool", "key", "--key-delay", "20", "29:1", "47:1", "47:0", "29:0"])  # ctrl+v
    elif shutil.which("xdotool"):
        proc = _run(["xdotool", "key", "ctrl+v"])
    else:
        raise InjectionError("no tool available to send the paste keystroke")
    # Surface failures instead of silently doing nothing.
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit code {proc.returncode}"
        raise InjectionError(f"paste keystroke failed: {detail}")
    # ydotoold processes the key sequence asynchronously — the command above
    # returns as soon as the events are queued, not delivered. Wait until they
    # have actually reached the focused window before touching the clipboard.
    time.sleep(0.35)


def _paste_text(text: str, *, restore: bool) -> None:
    previous = _clipboard_get() if restore else None
    if not _clipboard_set(text):
        raise InjectionError("could not set the clipboard")
    _paste_keypress()
    if restore and previous is not None:
        _clipboard_set(previous)


class YdotoolBackend(BaseBackend):
    name = "ydotool"

    def type_text(self, text: str) -> None:
        proc = _run(["ydotool", "type", "--key-delay", "8", "--", text])
        if proc.returncode != 0:
            raise InjectionError(f"ydotool type failed: {proc.stderr.strip()}")

    def paste(self, text: str, *, restore: bool = True) -> None:
        _paste_text(text, restore=restore)


class XdotoolBackend(BaseBackend):
    name = "xdotool"

    def type_text(self, text: str) -> None:
        _run(["xdotool", "type", "--delay", "8", "--", text])

    def paste(self, text: str, *, restore: bool = True) -> None:
        _paste_text(text, restore=restore)


class ClipboardBackend(BaseBackend):
    """Last resort: clipboard + paste shortcut only."""

    name = "clipboard"

    def type_text(self, text: str) -> None:
        self.paste(text, restore=False)

    def paste(self, text: str, *, restore: bool = True) -> None:
        _paste_text(text, restore=restore)


def _ydotoold_alive() -> bool:
    proc = _run(["pgrep", "-x", "ydotoold"], timeout=1.0)
    return proc.returncode == 0
