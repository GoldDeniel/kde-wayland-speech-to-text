// Expanding breathing ring for the recording state.
// `level` (0..1) modulates the expansion speed and opacity.

import QtQuick

Rectangle {
    id: ring

    property bool running: false
    property real level: 0.0
    property int delay: 0

    anchors.centerIn: parent
    width: 34
    height: 34
    radius: 34
    color: "transparent"
    border.width: 2
    border.color: Qt.rgba(0.6, 0.6, 0.6, 0.9 * opacityFactor)
    visible: running

    property real opacityFactor: 0.0

    SequentialAnimation {
        id: pulse
        running: ring.running
        loops: Animation.Infinite

        PauseAnimation { duration: ring.delay }

        ParallelAnimation {
            NumberAnimation {
                target: ring
                property: "width"
                from: 34
                to: 34 + 56 + ring.level * 26
                duration: 1400
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: ring
                property: "height"
                from: 34
                to: 34 + 56 + ring.level * 26
                duration: 1400
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: ring
                property: "opacityFactor"
                from: 0.9
                to: 0.0
                duration: 1400
                easing.type: Easing.InQuad
            }
        }
    }

    onRunningChanged: {
        if (!running) {
            ring.width = 34
            ring.height = 34
            ring.opacityFactor = 0.0
        }
    }
}
