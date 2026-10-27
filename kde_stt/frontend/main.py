"""kde-stt-frontend — Qt Quick overlay for KDE Plasma 6.

A tiny, frameless, always-on-top window that appears near the top-center of
the screen and animates the daemon's state:

  - idle      : hidden
  - recording : pulsing red dot, scale follows the live mic amplitude
  - processing: amber spinning ring
  - injecting : green flash
  - error     : red flash with a message

Stays above windows via a KWin window rule created by install/install.sh
(Wayland apps can't force themselves on top).

Run:  kde-stt-frontend
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .. import BUS_IFACE, BUS_NAME, BUS_PATH

QML_PATH = os.path.join(os.path.dirname(__file__), "overlay.qml")


class StateBridge(QObject):
    """Exposes the daemon's D-Bus signals to QML."""

    stateChanged = Signal(str)
    amplitudeChanged = Signal(float)
    transcriptionReady = Signal(str, int)
    errorReceived = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state = "idle"
        self._amplitude = 0.0
        self._connect()

    # -- properties exposed to QML ----------------------------------------

    @Property(str, notify=stateChanged)
    def state(self) -> str:  # type: ignore[valid-type]
        return self._state

    @Property(float, notify=amplitudeChanged)
    def amplitude(self) -> float:  # type: ignore[valid-type]
        return self._amplitude

    # -- D-Bus wiring ------------------------------------------------------

    def _connect(self) -> None:
        bus = QDBusConnection.sessionBus()
        if not bus.connect(BUS_NAME, BUS_PATH, BUS_IFACE, "StateChanged", self, "1_on_state(QString)"):
            print("warning: could not connect to StateChanged; is kde-sttd running?")
        bus.connect(BUS_NAME, BUS_PATH, BUS_IFACE, "Amplitude", self, "1_on_amplitude(double)")
        bus.connect(BUS_NAME, BUS_PATH, BUS_IFACE, "TranscriptionReady", self, "1_on_ready(QDBusMessage)")
        bus.connect(BUS_NAME, BUS_PATH, BUS_IFACE, "Error", self, "1_on_error(QString)")

    @Slot(str)
    def _on_state(self, state: str) -> None:
        self._state = state
        self.stateChanged.emit(state)

    @Slot(float)
    def _on_amplitude(self, level: float) -> None:
        self._amplitude = level
        self.amplitudeChanged.emit(level)

    @Slot(QDBusMessage)
    def _on_ready(self, message: QDBusMessage) -> None:
        args = message.arguments()
        text = args[0] if len(args) > 0 else ""
        ms = int(args[1]) if len(args) > 1 else 0
        self.transcriptionReady.emit(text, ms)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.errorReceived.emit(message)


def main() -> None:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("kde-stt-frontend")
    engine = QQmlApplicationEngine()
    bridge = StateBridge()
    engine.rootContext().setContextProperty("daemon", bridge)
    engine.load(QUrl.fromLocalFile(QML_PATH))
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
