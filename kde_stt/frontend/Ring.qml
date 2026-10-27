// Expanding "sonar" ring used while the assistant is listening.
// The ring starts at the size of the chip, then blooms outwards and fades.
// `level` (0..1) makes the bloom react to the live microphone level.

import QtQuick

Rectangle {
    id: ring

    property bool running: false
    property real level: 0.0
    property int delay: 0

    property color tint: "#ff4d6f"
    property real fromWidth: 34
    property real fromHeight: 34
    property real spreadX: 44
    property real spreadY: 26
    property real strokeWidth: 1.5

    anchors.centerIn: parent
    width: fromWidth
    height: fromHeight
    radius: height / 2
    color: "transparent"
    border.width: strokeWidth
    border.color: Qt.rgba(ring.tint.r, ring.tint.g, ring.tint.b, 0.7 * ring.fade)
    visible: running

    property real fade: 0.0

    Behavior on tint {
        ColorAnimation { duration: 320; easing.type: Easing.OutCubic }
    }

    SequentialAnimation {
        id: pulse
        running: ring.running
        loops: Animation.Infinite

        PauseAnimation { duration: ring.delay }

        ParallelAnimation {
            NumberAnimation {
                target: ring
                property: "width"
                from: ring.fromWidth
                to: ring.fromWidth + ring.spreadX + ring.level * 22
                duration: 1900
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: ring
                property: "height"
                from: ring.fromHeight
                to: ring.fromHeight + ring.spreadY + ring.level * 22
                duration: 1900
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: ring
                property: "fade"
                from: 0.8
                to: 0.0
                duration: 1900
                easing.type: Easing.InQuad
            }
        }
    }

    onRunningChanged: {
        if (!running) {
            ring.width = ring.fromWidth
            ring.height = ring.fromHeight
            ring.fade = 0.0
        }
    }
}
