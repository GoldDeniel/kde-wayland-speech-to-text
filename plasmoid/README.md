# Plasmoid (optional, future module)

A native Plasma applet that lives in the system tray and mirrors the daemon
state — a second, more "Plasma-native" frontend alongside the Qt Quick overlay.

**Why it's not implemented yet:** QML plasmoids cannot speak D-Bus directly;
they need a small C++ plugin (`KDeclarative` / `QDBusInterface`) compiled
against the KDE Frameworks version of your Plasma. The overlay frontend
(`kde_stt/frontend/`) covers the "animated dot" use case today.

When you want the tray applet later:

1. `kde-sttd` already exposes everything needed:
   - `io.github.golddeniel.STT` on the session bus
   - signals: `StateChanged`, `Amplitude`, `TranscriptionReady`, `Error`
2. Add a C++ plasmoid plugin that wraps `QDBusConnection::sessionBus()` and
   exposes the state as a Q_PROPERTY.
3. Package it with `kpackagetool6 --type Plasma/Applet --install plasmoid/`.

Suggested package layout:

```
plasmoid/
└── org.kde.kde-stt/
    ├── contents/ui/main.qml
    ├── metadata.json
    └── src/          # C++ D-Bus plugin
```
