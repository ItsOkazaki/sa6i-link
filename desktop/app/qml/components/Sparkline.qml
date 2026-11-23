// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import sa6i.link

// A line of samples, oldest at the left, newest at the right.
//
// A `null` in `points` is a moment that was never measured, and it is drawn as
// a gap: the line stops and starts again instead of dropping to zero. A dropped
// sample and an idle machine would otherwise look the same, which is the one
// thing this page must never do.
Item {
    id: line
    /// Numbers between 0 and 1, or nulls where nothing was measured.
    property var points: []
    property color color: Theme.primary
    property real stroke: 2

    onPointsChanged: canvas.requestPaint()

    function repaint() {
        canvas.requestPaint()
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const pts = line.points
            const count = pts ? pts.length : 0
            if (count === 0 || width <= 0 || height <= 0)
                return
            ctx.strokeStyle = line.color
            ctx.fillStyle = line.color
            ctx.lineWidth = line.stroke
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            const step = count > 1 ? width / (count - 1) : 0
            const yOf = v => height - Math.max(0, Math.min(1, v)) * (height - line.stroke) - line.stroke / 2
            let drawing = false
            let measured = 0
            let onlyX = 0
            let onlyY = 0
            for (let i = 0; i < count; i++) {
                const value = pts[i]
                if (value === null || value === undefined) {
                    // The gap: finish the run, draw nothing across it.
                    if (drawing)
                        ctx.stroke()
                    drawing = false
                    continue
                }
                const x = count > 1 ? i * step : width
                const y = yOf(value)
                measured++
                onlyX = x
                onlyY = y
                if (drawing) {
                    ctx.lineTo(x, y)
                } else {
                    ctx.beginPath()
                    ctx.moveTo(x, y)
                    drawing = true
                }
            }
            if (drawing)
                ctx.stroke()
            // One measured moment is a dot, not nothing.
            if (measured === 1) {
                ctx.beginPath()
                ctx.arc(onlyX, onlyY, line.stroke, 0, Math.PI * 2)
                ctx.fill()
            }
        }
    }
}
