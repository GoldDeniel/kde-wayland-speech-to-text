"""faster-whisper wrapper. The model is loaded once and kept warm."""

from __future__ import annotations

import time
from dataclasses import dataclass

from faster_whisper import WhisperModel

from .config import TranscriberConfig


@dataclass
class TranscriptionResult:
    text: str
    language: str
    inference_ms: int


class Transcriber:
    def __init__(self, cfg: TranscriberConfig):
        self.cfg = cfg
        device = cfg.resolved_device()
        self.model = WhisperModel(
            cfg.model,
            device=device,
            compute_type=cfg.resolved_compute_type(device),
            download_root=str(_download_root()),
        )

    def transcribe(self, audio) -> TranscriptionResult:
        start = time.perf_counter()
        segments, info = self.model.transcribe(
            audio,
            language=None if self.cfg.language == "auto" else self.cfg.language,
            beam_size=self.cfg.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = "".join(segment.text for segment in segments).strip()
        inference_ms = int((time.perf_counter() - start) * 1000)
        return TranscriptionResult(
            text=text,
            language=info.language or "unknown",
            inference_ms=inference_ms,
        )


def _download_root():
    from .config import MODEL_CACHE_DIR

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_CACHE_DIR
