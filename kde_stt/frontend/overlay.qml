// kde-stt-frontend overlay — a round glass AI assistant button.
//
// States: idle (hidden) | recording (listening) | processing (thinking)
//         | injecting (done) | error
//
// Minimal by design: a single circular button. The live waveform, the
// thinking star, the success tick and the error mark all share the same
// spot in the centre of the sphere.

import QtQuick
import QtQuick.Window
import QtQuick.Effects
import QtQuick.Shapes

Window {
    id: root

    visible: false
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    title: "kde-stt overlay"

    // Placement and size come from [frontend] in ~/.config/kde-stt/config.toml.
    property int buttonSize: configButtonSize
    property string overlayPosition: configOverlayPosition
    property int screenMargin: configScreenMargin

    readonly property real u: buttonSize / 88.0
    readonly property int glowPadding: Math.round(Math.max(56, buttonSize * 0.36))
    readonly property bool onLeft: overlayPosition.indexOf("left") >= 0
    readonly property bool onRight: overlayPosition.indexOf("right") >= 0
    readonly property bool onTop: overlayPosition.indexOf("top") >= 0
    readonly property bool onBottom: overlayPosition.indexOf("bottom") >= 0
    readonly property int padLeft: onLeft ? Math.min(glowPadding, screenMargin) : glowPadding
    readonly property int padRight: onRight ? Math.min(glowPadding, screenMargin) : glowPadding
    readonly property int padTop: onTop ? Math.min(glowPadding, screenMargin) : glowPadding
    readonly property int padBottom: onBottom ? Math.min(glowPadding, screenMargin) : glowPadding

    width: padLeft + buttonSize + padRight
    height: padTop + buttonSize + padBottom

    x: {
        if (onLeft)
            return Math.round(screenMargin - padLeft)
        if (onRight)
            return Math.round(Screen.width - width - screenMargin + padRight)
        return Math.round((Screen.width - width) / 2)
    }
    y: {
        if (onTop)
            return Math.round(screenMargin - padTop)
        if (onBottom)
            return Math.round(Screen.height - height - screenMargin + padBottom)
        return Math.round((Screen.height - height) / 2)
    }

    // daemon properties from the Python bridge
    property string state: daemon ? daemon.state : "idle"
    property real amplitude: daemon ? daemon.amplitude : 0.0
    property string errorMessage: ""

    // While an outcome is on screen, ignore the daemon's immediate return to
    // idle. This gives "Done" and errors enough time to actually be seen.
    property string heldState: ""
    property real time: 0.0

    readonly property bool live: state !== "idle"
    readonly property bool recording: state === "recording"
    readonly property bool processing: state === "processing"
    readonly property bool success: state === "injecting"
    readonly property bool failed: state === "error"

    property color accent: recording ? "#facc15"
                        : processing ? "#8b5cf6"
                        : success ? "#2dd4a7"
                        : failed ? "#b91c1c"
                        : "#64748b"
    property color accentDeep: recording ? "#ca8a04"
                           : processing ? "#4c1d95"
                           : success ? "#047857"
                           : failed ? "#7f1d1d"
                           : "#334155"

    Behavior on accent {
        ColorAnimation { duration: 360; easing.type: Easing.OutCubic }
    }
    Behavior on accentDeep {
        ColorAnimation { duration: 360; easing.type: Easing.OutCubic }
    }

    function barLevel(i) {
        var center = 1.0 - Math.abs(i - 3) * 0.1
        var phase = time * (8.0 + (i % 3) * 1.4) + i * 1.15
        var wave = 0.5 + 0.5 * Math.sin(phase)
        var energy = 0.22 + 0.78 * Math.min(amplitude * 3.2, 1.0)
        return Math.max(0.08, wave * center * energy)
    }

    function hold(nextState, ms) {
        heldState = nextState
        state = nextState
        holdTimer.interval = ms
        holdTimer.restart()
    }

    onStateChanged: {
        var show = state !== "idle"
        if (show) {
            if (!visible) {
                // Let the Python side re-read ~/.config/kde-stt/config.toml
                // before the window is mapped, so the next appearance uses
                // the latest [frontend] settings.
                root.overlayWillShow()
                intro.restart()
            }
            stateFlash.restart()
        }
        visible = show
        time = 0.0
    }

    Component.onCompleted: {
        if (state !== "idle") {
            visible = true
            intro.restart()
        }
    }

    Connections {
        target: daemon

        function onStateChanged(s) {
            if (root.heldState !== "") {
                // A new recording (or a fresh error) always wins over a
                // lingering outcome.
                if (s === "recording" || s === "processing" || s === "error") {
                    root.heldState = ""
                    holdTimer.stop()
                    root.state = s
                }
                return
            }

            root.state = s

            // The daemon flips back to idle almost immediately after injecting.
            if (s === "injecting")
                root.hold("injecting", 950)
        }

        function onAmplitudeChanged(a) {
            root.amplitude = a
        }

        function onErrorReceived(m) {
            root.errorMessage = m
            root.hold("error", 3000)
        }

        function onTranscriptionReady(text, ms) {
            root.transcriptionReady(text, ms)
            if (root.heldState === "")
                root.hold("injecting", 950)
        }
    }

    Timer {
        id: holdTimer
        onTriggered: {
            root.heldState = ""
            root.errorMessage = ""
            root.state = daemon ? daemon.state : "idle"
        }
    }

    Timer {
        id: waveTimer
        interval: 33
        repeat: true
        running: root.recording
        onTriggered: root.time += 0.033
    }

    // ---------------------------------------------------------------- center

    Item {
        id: stage
        x: root.padLeft
        y: root.padTop
        width: root.buttonSize
        height: root.buttonSize

        // soft coloured aura behind the button
        Rectangle {
            id: aura
            anchors.centerIn: button
            width: button.width
            height: button.height
            radius: button.radius
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.58)
            opacity: root.live ? 0.82 : 0.0

            layer.enabled: true
            layer.effect: MultiEffect {
                blurEnabled: true
                blurMax: 48
                blur: 0.9
                autoPaddingEnabled: true
            }

            Behavior on opacity {
                NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
            }

            SequentialAnimation on scale {
                running: root.recording
                loops: Animation.Infinite
                NumberAnimation {
                    to: 1.08
                    duration: 1500
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    to: 0.98
                    duration: 1500
                    easing.type: Easing.InOutSine
                }
            }
        }

        // expanding sonar rings while listening
        Repeater {
            model: 3

            Ring {
                running: root.recording
                level: root.amplitude
                delay: index * 630
                tint: root.accent
                fromWidth: button.width
                fromHeight: button.height
                spreadX: button.width * 0.52
                spreadY: button.height * 0.52
            }
        }

        // diffuse drop shadow
        Rectangle {
            anchors.centerIn: button
            anchors.verticalCenterOffset: 10 * root.u
            width: button.width
            height: button.height
            radius: button.radius
            color: "#05060a"
            opacity: 0.6
            layer.enabled: true
            layer.effect: MultiEffect {
                blurEnabled: true
                blurMax: 40
                blur: 1.0
                autoPaddingEnabled: true
            }
        }

        // the button
        Rectangle {
            id: button
            anchors.centerIn: stage
            width: root.buttonSize
            height: root.buttonSize
            radius: width / 2
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.14)
            clip: true

            gradient: LinearGradient {
                x1: 0
                y1: 0
                x2: button.width
                y2: button.height

                GradientStop { position: 0.0; color: "#282c3b" }
                GradientStop { position: 0.5; color: "#191b26" }
                GradientStop { position: 1.0; color: "#0d0e15" }
            }

            // state colour bleeding in behind the sphere
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                opacity: 0.9

                gradient: LinearGradient {
                    x1: 0
                    y1: 0
                    x2: button.width
                    y2: button.height

                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.35)
                    }
                    GradientStop {
                        position: 0.55
                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.08)
                    }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16)
                    }
                }
            }

            // brief colour wash whenever the assistant changes state
            Rectangle {
                id: cardFlash
                anchors.fill: parent
                radius: parent.radius
                color: root.accent
                opacity: 0.0
            }

            // soft halo just outside the sphere
            Rectangle {
                anchors.centerIn: parent
                width: 84 * root.u
                height: 84 * root.u
                radius: width / 2
                opacity: 0.9

                gradient: RadialGradient {
                    centerX: 42 * root.u
                    centerY: 42 * root.u
                    centerRadius: 42 * root.u

                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.55)
                    }
                    GradientStop {
                        position: 0.6
                        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                    }
                    GradientStop {
                        position: 1.0
                        color: "transparent"
                    }
                }
            }

            // orbiting dots while the model is thinking
            Item {
                id: orbit
                anchors.centerIn: parent
                width: 84 * root.u
                height: 84 * root.u
                visible: root.processing

                RotationAnimation on rotation {
                    running: root.processing
                    from: 0
                    to: 360
                    duration: 1500
                    loops: Animation.Infinite
                }

                Repeater {
                    model: 8

                    Rectangle {
                        width: 3 * root.u
                        height: 3 * root.u
                        radius: width / 2
                        color: root.accent
                        opacity: 1.0 - index * 0.105
                        x: 42 * root.u + Math.cos(index * Math.PI / 4) * 38 * root.u - width / 2
                        y: 42 * root.u + Math.sin(index * Math.PI / 4) * 38 * root.u - height / 2
                    }
                }
            }

            // the sphere
            Rectangle {
                id: orb
                anchors.centerIn: parent
                width: 72 * root.u
                height: 72 * root.u
                radius: width / 2
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.22)

                scale: root.recording
                       ? 1.0 + Math.min(root.amplitude * 0.32, 0.08)
                       : 1.0
                Behavior on scale {
                    NumberAnimation { duration: 90; easing.type: Easing.OutQuad }
                }

                gradient: RadialGradient {
                    centerX: 25 * root.u
                    centerY: 21 * root.u
                    centerRadius: 51 * root.u
                    focalX: 23 * root.u
                    focalY: 19 * root.u

                    GradientStop {
                        position: 0.0
                        color: Qt.lighter(root.accent, 1.65)
                    }
                    GradientStop {
                        position: 0.4
                        color: root.accent
                    }
                    GradientStop {
                        position: 1.0
                        color: root.accentDeep
                    }
                }

                // glassy highlight
                Rectangle {
                    x: 13 * root.u
                    y: 8 * root.u
                    width: 25 * root.u
                    height: 15 * root.u
                    radius: 9 * root.u
                    rotation: -22
                    color: "white"
                    opacity: 0.22
                }

                // live waveform, in white, inside the sphere
                Row {
                    anchors.centerIn: parent
                    spacing: 4 * root.u
                    visible: root.recording

                    Repeater {
                        model: 7

                        Item {
                            width: 3 * root.u
                            height: 30 * root.u

                            Rectangle {
                                anchors.centerIn: parent
                                width: 3 * root.u
                                radius: width / 2
                                height: 4 * root.u + 20 * root.u * root.barLevel(index)
                                color: "#ffffff"
                                opacity: 0.95

                                Behavior on height {
                                    NumberAnimation {
                                        duration: 120
                                        easing.type: Easing.OutQuad
                                    }
                                }
                            }
                        }
                    }
                }

                // thinking star
                Shape {
                    anchors.centerIn: parent
                    width: 15 * root.u
                    height: 15 * root.u
                    visible: root.processing
                    opacity: 0.95
                    layer.enabled: true
                    layer.samples: 4

                    ShapePath {
                        fillColor: "white"
                        strokeColor: "transparent"

                        startX: 7.5 * root.u
                        startY: 0
                        PathLine { x: 8.9 * root.u; y: 6.1 * root.u }
                        PathLine { x: 15 * root.u; y: 7.5 * root.u }
                        PathLine { x: 8.9 * root.u; y: 8.9 * root.u }
                        PathLine { x: 7.5 * root.u; y: 15 * root.u }
                        PathLine { x: 6.1 * root.u; y: 8.9 * root.u }
                        PathLine { x: 0; y: 7.5 * root.u }
                        PathLine { x: 6.1 * root.u; y: 6.1 * root.u }
                        PathLine { x: 7.5 * root.u; y: 0 }
                    }

                    SequentialAnimation on scale {
                        running: root.processing
                        loops: Animation.Infinite
                        NumberAnimation {
                            to: 1.12
                            duration: 1200
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            to: 0.88
                            duration: 1200
                            easing.type: Easing.InOutSine
                        }
                    }
                }

                // success tick
                Canvas {
                    width: 24 * root.u
                    height: 24 * root.u
                    anchors.centerIn: parent
                    visible: root.success
                    onVisibleChanged: if (visible) requestPaint()
                    onWidthChanged: if (visible) requestPaint()

                    onPaint: {
                        var ctx = getContext("2d")
                        var s = root.u
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "#ffffff"
                        ctx.lineWidth = 2.6 * s
                        ctx.lineCap = "round"
                        ctx.lineJoin = "round"
                        ctx.beginPath()
                        ctx.moveTo(4 * s, 12 * s)
                        ctx.lineTo(10 * s, 18 * s)
                        ctx.lineTo(21 * s, 5 * s)
                        ctx.stroke()
                    }
                }

                // error mark
                Text {
                    anchors.centerIn: parent
                    visible: root.failed
                    text: "!"
                    color: "#ffffff"
                    font.pixelSize: Math.max(12, Math.round(24 * root.u))
                    font.weight: Font.Bold
                }
            }
        }
    }

    // springy entrance
    ParallelAnimation {
        id: intro
        NumberAnimation {
            target: stage
            property: "scale"
            from: 0.82
            to: 1.0
            duration: 520
            easing.type: Easing.OutBack
            easing.overshoot: 1.18
        }
        NumberAnimation {
            target: stage
            property: "opacity"
            from: 0.0
            to: 1.0
            duration: 240
            easing.type: Easing.OutCubic
        }
    }

    // state-change colour wash
    NumberAnimation {
        id: stateFlash
        target: cardFlash
        property: "opacity"
        from: 0.22
        to: 0.0
        duration: 520
        easing.type: Easing.OutCubic
    }

    // fade in/out
    opacity: visible ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    signal transcriptionReady(string text, int ms)
    signal overlayWillShow()
}
