// kde-stt-frontend overlay — a small, beautiful animated dot.
// States: idle (hidden) | recording (pulsing red) | processing (amber ring)
//         | injecting (green flash) | error (red flash)

import QtQuick
import QtQuick.Window

Window {
    id: root

    visible: false
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    title: "kde-stt overlay"
    width: 220
    height: 220
    x: Screen.width / 2 - width / 2
    y: 96

    // daemon properties from the Python bridge
    property string state: daemon ? daemon.state : "idle"
    property real amplitude: daemon ? daemon.amplitude : 0.0
    property string errorMessage: ""

    onStateChanged: {
        root.visible = (root.state !== "idle")
        if (root.state === "error") flashTimer.restart()
        else if (root.state === "injecting") flashTimer.restart()
    }

    Connections {
        target: daemon
        function onStateChanged(s) { root.state = s }
        function onAmplitudeChanged(a) { root.amplitude = a }
        function onErrorReceived(m) { root.errorMessage = m; root.state = "error" }
    }

    Timer {
        id: flashTimer
        interval: 450
        onTriggered: { root.state = "idle" }
    }

    Timer {
        id: hideTimer
        interval: 2500
        onTriggered: { root.visible = false; root.errorMessage = "" }
    }

    // ---------------------------------------------------------------- center

    Item {
        id: stage
        anchors.centerIn: parent
        width: 120
        height: 120

        // expanding breathing rings (recording)
        Repeater {
            model: 3
            Ring {
                delay: index * 700
                running: root.state === "recording"
                level: root.amplitude
            }
        }

        // the dot itself
        Rectangle {
            id: dot
            anchors.centerIn: parent
            width: 34
            height: 34
            radius: 17

            color: {
                if (root.state === "error") return "#ff4d5e"
                if (root.state === "injecting") return "#34d399"
                if (root.state === "processing") return "#fbbf24"
                return "#3c3c3c"
            }

            // glow
            layer.enabled: true
            layer.effect: null

            // live amplitude: dot grows slightly with the voice
            scale: 1.0 + Math.min(root.amplitude * 0.7, 0.7)
            Behavior on scale {
                NumberAnimation { duration: 90; easing.type: Easing.OutQuad }
            }

            // processing: gentle spin
            RotationAnimation on rotation {
                running: root.state === "processing"
                from: 0; to: 360
                duration: 1100
                loops: Animation.Infinite
            }

            // subtle inner highlight
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.4
                height: parent.height * 0.4
                radius: width / 2
                color: Qt.lighter(parent.color, 1.35)
                opacity: 0.85
            }
        }
    }

    // fade in/out
    opacity: visible ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    onTranscriptionReady: {
        // brief green confirmation then hide
        root.state = "injecting"
        hideTimer.restart()
    }

    signal transcriptionReady(string text, int ms)
    Connections {
        target: daemon
        function onTranscriptionReady(text, ms) { root.transcriptionReady(text, ms) }
    }
}
