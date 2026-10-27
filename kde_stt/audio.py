"""Microphone capture via PipeWire's PulseAudio-compatible API.

Captures 16 kHz mono int16 frames — exactly what whisper expects — and keeps a
running RMS amplitude so the overlay can animate to the actual voice level.
"""

from __future__ import annotations

import threading
from typing import Callable

import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        input_device: int | None = None,
        on_amplitude: Callable[[float], None] | None = None,
    ):
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.on_amplitude = on_amplitude
        self._lock = threading.Lock()
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._device_name: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                raise RuntimeError("already recording")
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=1024,
                device=self.input_device,
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            pass  # buffer overruns are non-fatal; whisper tolerates gaps
        with self._lock:
            self._frames.append(indata.copy())
        if self.on_amplitude is not None:
            self.on_amplitude(_rms(indata))

    def stop(self) -> np.ndarray | None:
        with self._lock:
            stream, self._stream = self._stream, None
            frames = self._frames
            self._frames = []
        if stream is None:
            return None
        stream.stop()
        stream.close()
        if not frames:
            return None
        return np.concatenate(frames)

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def duration(self) -> float:
        with self._lock:
            n = len(self._frames)
        return n * 1024 / self.sample_rate


def _rms(frame: np.ndarray) -> float:
    """Normalize a frame of int16 samples to a 0..1 loudness value."""
    if frame.size == 0:
        return 0.0
    peak = float(np.abs(frame).max())
    return min(peak / 32768.0, 1.0)
