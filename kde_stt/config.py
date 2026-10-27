"""Configuration loaded from ~/.config/kde-stt/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "kde-stt"
CONFIG_FILE = CONFIG_DIR / "config.toml"
MODEL_CACHE_DIR = Path.home() / ".cache" / "kde-stt"


def _detect_device() -> str:
    """Return 'cuda' if a CUDA runtime is available, else 'cpu'."""
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


@dataclass
class TranscriberConfig:
    model: str = "small"
    device: str = "auto"  # auto | cpu | cuda
    compute_type: str = "auto"  # auto | int8 | float16 | float32
    language: str = "auto"  # auto-detect or ISO code
    beam_size: int = 5

    def resolved_device(self) -> str:
        return _detect_device() if self.device == "auto" else self.device

    def resolved_compute_type(self, device: str) -> str:
        if self.compute_type != "auto":
            return self.compute_type
        # int8 quantization is a good speed/quality trade-off on CPU;
        # on GPU float16 is both faster and more accurate.
        return "float16" if device == "cuda" else "int8"


@dataclass
class InjectorConfig:
    mode: str = "paste"  # paste | type
    # When True the previous clipboard content is restored after a paste;
    # when False the transcribed text stays on the clipboard (handy for reuse).
    restore_clipboard: bool = False


@dataclass
class ShortcutConfig:
    """How the user triggers recording.

    toggle : a normal global shortcut calls `kde-stt toggle` (press = start,
             press again = stop). Works with any desktop environment.
    push   : hold a physical key to talk; release to transcribe. The daemon
             watches the key directly via evdev, so no compositor shortcut is
             needed at all. Requires read access to /dev/input/event* (the
             'input' group).
    """
    mode: str = "toggle"  # toggle | push
    push_key: str = "left-ctrl"  # evdev key name for push mode (left-ctrl, right-ctrl, f9, ...)
    push_devices: list[str] = field(default_factory=list)  # /dev/input/eventX; empty = scan all


@dataclass
class Config:
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    shortcut: ShortcutConfig = field(default_factory=ShortcutConfig)
    sample_rate: int = 16000  # whisper requires 16 kHz
    input_device: int | None = None  # None = PipeWire default
    max_recording_s: int = 120  # hard stop, protects against runaway captures


def load_config() -> Config:
    cfg = Config()
    if not CONFIG_FILE.exists():
        return cfg
    try:
        raw = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(f"warning: ignoring malformed config: {exc}")
        return cfg
    for section, dataclass_type in (
        ("transcriber", TranscriberConfig),
        ("injector", InjectorConfig),
        ("shortcut", ShortcutConfig),
    ):
        if section in raw:
            overrides = {
                k: v for k, v in raw[section].items() if hasattr(dataclass_type, k)
            }
            section_obj = getattr(cfg, section)
            for k, v in overrides.items():
                setattr(section_obj, k, v)
    if "sample_rate" in raw:
        cfg.sample_rate = int(raw["sample_rate"])
    if "input_device" in raw:
        cfg.input_device = raw["input_device"]
    if "max_recording_s" in raw:
        cfg.max_recording_s = int(raw["max_recording_s"])
    return cfg


def example_config() -> str:
    return """\
# ~/.config/kde-stt/config.toml
[transcriber]
model = "small"          # tiny | base | small | medium | large-v3
device = "auto"          # auto | cpu | cuda
compute_type = "auto"    # auto | int8 | float16 | float32
language = "auto"        # auto-detect, or "en", "pl", ...
beam_size = 5

[injector]
mode = "paste"           # paste (clipboard+Ctrl+V) | type (key-by-key)
restore_clipboard = false  # false = keep the transcribed text on the clipboard

[shortcut]
mode = "toggle"          # toggle (DE shortcut) | push (hold a key, release to transcribe)
push_key = "left-ctrl"   # key to hold in push mode; needs 'input' group access
"""
