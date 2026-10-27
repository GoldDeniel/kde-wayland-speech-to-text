# KDE-STT — future GNOME Shell extension

The daemon (`kde-sttd`) and CLI (`kde-stt`) are desktop-agnostic: they speak
D-Bus on the session bus. A GNOME Shell extension would:

1. Subscribe to `io.github.golddeniel.STT` signals (`StateChanged`, `Amplitude`,
   `TranscriptionReady`, `Error`) via `Gio.DBus`.
2. Draw the animated dot in a panel indicator or a shell OSD.
3. Bind the global shortcut via `gsettings custom-keybinding` instead of
   KDE's "Custom Shortcuts".

Reference layout for later:

```
gnome/
└── org.gnome.shell.extensions.kde-stt/
    ├── extension.js
    ├── metadata.json
    └── indicator.js
```

GNOME text injection uses the same `ydotool` backend as KDE — no change needed
in `kde_stt/injector.py`.
