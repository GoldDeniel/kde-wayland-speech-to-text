"""Configuration loaded from ~/.config/kde-stt/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "kde-stt"
CONFIG_FILE = CONFIG_DIR / "config.toml"
MODEL_CACHE_DIR = Path.home() / ".cache" / "kde-stt"

FRONTEND_POSITIONS = {
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
}

# Friendly shorthands accepted in config.toml.
FRONTEND_POSITION_ALIASES = {
    "middle": "center",
    "top": "top-center",
    "top-middle": "top-center",
    "bottom": "bottom-center",
    "bottom-middle": "bottom-center",
    "left": "middle-left",
    "right": "middle-right",
}


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
class FrontendConfig:
    """Placement and size of the Qt Quick overlay.

    position: one of top-left, top-center, top-right, middle-left, center,
              middle-right, bottom-left, bottom-center, bottom-right.
    size:     diameter of the round button in logical pixels.
    margin:   gap between the button and the screen edge, in pixels.
    """
    position: str = "top-center"
    size: int = 88
    margin: int = 64

    def resolved_position(self) -> str:
        value = str(self.position).strip().lower()
        value = FRONTEND_POSITION_ALIASES.get(value, value)
        if value not in FRONTEND_POSITIONS:
            print(
                f"warning: unknown frontend.position {self.position!r}; "
                "using 'top-center'"
            )
            return "top-center"
        return value

    def resolved_size(self) -> int:
        try:
            value = int(self.size)
        except (TypeError, ValueError):
            return 88
        return max(48, min(value, 240))

    def resolved_margin(self) -> int:
        try:
            value = int(self.margin)
        except (TypeError, ValueError):
            return 64
        return max(0, min(value, 400))


@dataclass
class Config:
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    shortcut: ShortcutConfig = field(default_factory=ShortcutConfig)
    frontend: FrontendConfig = field(default_factory=FrontendConfig)
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
        ("frontend", FrontendConfig),
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


def load_frontend_config() -> FrontendConfig | None:
    """Load only the [frontend] section for the overlay's live refresh.

    Returns None when the file exists but cannot be parsed, so a half-saved
    edit does not reset a running overlay to defaults.
    """
    if not CONFIG_FILE.exists():
        return FrontendConfig()
    try:
        raw = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"warning: ignoring malformed config: {exc}")
        return None
    cfg = FrontendConfig()
    section = raw.get("frontend", {})
    if isinstance(section, dict):
        for key, value in section.items():
            if hasattr(FrontendConfig, key):
                setattr(cfg, key, value)
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

[frontend]
position = "bottom-center"  # top-left | top-center | top-right
                            # middle-left | center | middle-right
                            # bottom-left | bottom-center | bottom-right
size = 80                   # round button diameter in pixels (48-240)
margin = 64                 # gap from the screen edge in pixels
"""
