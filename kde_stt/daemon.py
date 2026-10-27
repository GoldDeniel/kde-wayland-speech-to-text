"""kde-sttd — the core daemon.

Listens on the session bus (io.github.golddeniel.STT) for commands from the
CLI and global shortcut, records audio, transcribes it, and injects the text.
It emits signals so any frontend (Qt overlay, Plasma applet, GNOME extension)
can reflect state without knowing anything about whisper.

Run:  kde-sttd
"""

import asyncio
import json
import logging
import os
import signal
import threading

from dbus_next.constants import BusType
from dbus_next.aio.message_bus import MessageBus
from dbus_next.service import ServiceInterface, method as dbus_method, signal as dbus_signal

from .audio import Recorder
from . import BUS_IFACE, BUS_NAME, BUS_PATH
from .config import Config, load_config
from .injector import Injector, InjectionError
from .push import PushToTalkWatcher
from .transcriber import Transcriber

log = logging.getLogger("kde-sttd")

STATES = ("idle", "recording", "processing", "injecting")


class STTService(ServiceInterface):
    def __init__(self, app: "Daemon"):
        super().__init__(BUS_IFACE)
        self.app = app

    # -- commands ---------------------------------------------------------

    @dbus_method(name="Start")
    def start(self) -> None:
        self.app.start_recording()

    @dbus_method(name="Stop")
    def stop(self) -> None:
        self.app.stop_and_transcribe()

    @dbus_method(name="Toggle")
    def toggle(self) -> None:
        self.app.toggle()

    @dbus_method(name="Cancel")
    def cancel(self) -> None:
        self.app.cancel()

    @dbus_method(name="Status")
    def status(self) -> "s":  # type: ignore
        return json.dumps(self.app.status())

    @dbus_method(name="Inject")
    def inject(self, text: "s") -> None:  # type: ignore
        """Debug helper: run the injection pipeline without recording."""
        self.app.inject_text(text)

    # -- signals ----------------------------------------------------------

    @dbus_signal(name="StateChanged")
    def StateChanged(self, state: "s") -> "s":  # type: ignore
        return state

    @dbus_signal(name="Amplitude")
    def Amplitude(self, level: "d") -> "d":  # type: ignore
        return level

    @dbus_signal(name="TranscriptionReady")
    def TranscriptionReady(self, text: "s", inference_ms: "i") -> "si":  # type: ignore
        return [text, inference_ms]

    @dbus_signal(name="Error")
    def Error(self, message: "s") -> "s":  # type: ignore
        return message


class Daemon:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = "idle"
        self.last_text = ""
        self.last_language = ""
        self._service: STTService | None = None
        self._recorder = Recorder(
            sample_rate=cfg.sample_rate,
            input_device=cfg.input_device,
            on_amplitude=self._on_amplitude,
        )
        self._transcriber: Transcriber | None = None
        self._injector: Injector | None = None
        self._push_watcher: PushToTalkWatcher | None = None
        self._stop_event: asyncio.Event | None = None
        self._amplitude_throttle = threading.Lock()
        self._last_amp_emit = 0.0

    # -- state ------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self.state = state
        if self._service is not None:
            self._service.StateChanged(state)

    def _on_amplitude(self, level: float) -> None:
        # throttle D-Bus signal to ~30 Hz so the dot pulses without flooding
        import time

        now = time.perf_counter()
        with self._amplitude_throttle:
            if now - self._last_amp_emit < 1 / 30:
                return
            self._last_amp_emit = now
        if self._service is not None:
            self._service.Amplitude(level)

    def _emit_error(self, message: str) -> None:
        log.error(message)
        if self._service is not None:
            self._service.Error(message)

    def status(self) -> dict:
        return {
            "state": self.state,
            "model": self.cfg.transcriber.model,
            "last_text": self.last_text,
            "last_language": self.last_language,
        }

    # -- commands ---------------------------------------------------------

    def toggle(self) -> None:
        if self.state == "recording":
            self.stop_and_transcribe()
        elif self.state == "idle":
            self.start_recording()

    def start_recording(self) -> None:
        if self.state != "idle":
            return
        try:
            self._recorder.start()
        except Exception as exc:
            self._emit_error(f"could not start recording: {exc}")
            return
        self._set_state("recording")
        self._start_max_duration_guard()

    def stop_and_transcribe(self) -> None:
        if self.state != "recording":
            return
        audio = self._recorder.stop()
        self._set_state("processing")
        asyncio.get_event_loop().create_task(self._transcribe(audio))

    def cancel(self) -> None:
        """Discard an in-progress recording without transcribing it."""
        if self.state != "recording":
            return
        self._recorder.stop()
        self._set_state("idle")

    def inject_text(self, text: str) -> None:
        """Debug helper: inject text without a recording."""
        if self._injector is None:
            return
        log.info("debug inject request: %r", text)

        def _log_task_error(task: asyncio.Task) -> None:
            exc = task.exception()
            if exc is not None:
                log.error("debug inject failed: %s", exc)

        asyncio.get_event_loop().create_task(
            asyncio.to_thread(self._injector.inject, text)
        ).add_done_callback(_log_task_error)

    def request_stop(self) -> None:
        """Signal the main loop to exit (SIGTERM/SIGINT)."""
        if self._stop_event is not None:
            self._stop_event.set()

    def _start_max_duration_guard(self) -> None:
        async def guard() -> None:
            await asyncio.sleep(self.cfg.max_recording_s)
            if self.state == "recording":
                self._emit_error("recording exceeded max duration, stopping")
                self.stop_and_transcribe()

        asyncio.get_event_loop().create_task(guard())

    # -- transcription pipeline -------------------------------------------

    async def _transcribe(self, audio) -> None:
        try:
            if audio is None or len(audio) < self.cfg.sample_rate // 2:
                self._set_state("idle")
                return
            if self._transcriber is None:
                self._transcriber = Transcriber(self.cfg.transcriber)
            result = await asyncio.to_thread(self._transcriber.transcribe, audio)
            self.last_text = result.text
            self.last_language = result.language
            log.info(
                "transcribed: %r (%s, %d ms)",
                result.text[:120],
                result.language,
                result.inference_ms,
            )
            if not result.text:
                self._set_state("idle")
                self._emit_error("nothing recognizable was said")
                return
            self._set_state("injecting")
            assert self._injector is not None
            try:
                await asyncio.to_thread(self._injector.inject, result.text)
            except InjectionError as exc:
                self._emit_error(f"injection failed: {exc}")
            finally:
                self._set_state("idle")
            if self._service is not None:
                self._service.TranscriptionReady(result.text, result.inference_ms)
        except Exception as exc:
            log.exception("transcription failed")
            self._emit_error(f"transcription failed: {exc}")
            self._set_state("idle")

    # -- bootstrap ----------------------------------------------------------

    async def run(self) -> None:
        self._injector = Injector(self.cfg.injector)
        log.info("injection backend: %s", self._injector.describe())
        if self.cfg.shortcut.mode == "push":
            self._push_watcher = PushToTalkWatcher(
                self.cfg.shortcut,
                on_press=self.start_recording,
                on_release=self.stop_and_transcribe,
            )
            self._push_watcher.start()
        else:
            log.info("push-to-talk disabled (shortcut mode: %s)", self.cfg.shortcut.mode)
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._service = STTService(self)
        bus.export(BUS_PATH, self._service)
        await bus.request_name(BUS_NAME)
        log.info("daemon ready: %s on %s", BUS_NAME, BUS_PATH)
        log.info("model: %s", self.cfg.transcriber.model)
        self._stop_event = asyncio.Event()
        await self._stop_event.wait()
        log.info("daemon stopped")

    def _shutdown(self) -> None:
        if self._push_watcher is not None:
            self._push_watcher.stop()
        if self._recorder.recording:
            self._recorder.stop()
        self.request_stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    daemon = Daemon(cfg)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, daemon._shutdown)
        await daemon.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
