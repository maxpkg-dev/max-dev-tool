"""A toggle switch in the tool's look: a rounded track, a sliding knob and the label to its right.

It replaces check boxes everywhere. It behaves like a check box (`toggled`, `isChecked`, `setChecked`, `setEnabled`).
"""

from ..qt_compat import QtCore, QtGui, QtWidgets, Qt
from ..ui_scale import px
from .controls import Themed


def _mix(first, second, amount):
    return QtGui.QColor(int(first.red() + (second.red() - first.red()) * amount),
                        int(first.green() + (second.green() - first.green()) * amount),
                        int(first.blue() + (second.blue() - first.blue()) * amount))


class Switch(QtWidgets.QAbstractButton, Themed):
    TRACK_W, TRACK_H, GAP = 32, 18, 9  # Logical pixels at 100 %

    def __init__(self, theme, text="", parent=None):
        QtWidgets.QAbstractButton.__init__(self, parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self._position = 0.0  # 0 = off (knob left), 1 = on (knob right)
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(120)
        self._animation.valueChanged.connect(self._move)
        self.toggled.connect(self._slide)
        self._colors = theme.colors
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def setChecked(self, checked):
        QtWidgets.QAbstractButton.setChecked(self, checked)
        self._animation.stop()
        self._position = 1.0 if self.isChecked() else 0.0  # No animation for programmatic changes
        self.update()

    def _slide(self, checked):
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def _move(self, value):
        self._position = float(value)
        self.update()

    def sizeHint(self):
        text = self.text()
        width = px(self.TRACK_W) + (px(self.GAP) + self.fontMetrics().horizontalAdvance(text) if text else 0)
        return QtCore.QSize(width + px(2), max(px(self.TRACK_H), self.fontMetrics().height()) + px(6))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        colors = self._colors
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        enabled = self.isEnabled()
        track_w, track_h = px(self.TRACK_W), px(self.TRACK_H)
        top = (self.height() - track_h) / 2.0
        track = QtCore.QRectF(1, top, track_w, track_h)
        off_fill, on_fill = QtGui.QColor(colors["recessed"]), QtGui.QColor(colors["accent"])
        if not enabled:
            off_fill = on_fill = QtGui.QColor(colors["disabled_surface"])
            border = QtGui.QColor(colors["disabled_border"])
        elif self.hasFocus():
            border = QtGui.QColor(colors["focus"])
        elif self.underMouse():
            border = QtGui.QColor(colors["active_border"])
        else:
            border = _mix(QtGui.QColor(colors["checkbox_border"]), on_fill, self._position)
        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(_mix(off_fill, on_fill, self._position))
        painter.drawRoundedRect(track, track_h / 2.0, track_h / 2.0)
        margin = px(3)
        knob = track_h - 2 * margin
        x = track.left() + margin + (track_w - 2 * margin - knob) * self._position
        knob_color = QtGui.QColor(colors["disabled_text"] if not enabled else colors["muted_text"])
        if enabled:
            knob_color = _mix(knob_color, QtGui.QColor(colors["log_badge_text"]), self._position)
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(QtCore.QRectF(x, top + margin, knob, knob))
        if self.text():
            painter.setPen(QtGui.QColor(colors["text"] if enabled else colors["disabled_text"]))
            painter.setFont(self.font())
            area = QtCore.QRectF(track.right() + px(self.GAP), 0, self.width() - track.right() - px(self.GAP), self.height())
            painter.drawText(area, int(Qt.AlignVCenter | Qt.AlignLeft), self.text())
        painter.end()

    def enterEvent(self, event):
        self.update()
        QtWidgets.QAbstractButton.enterEvent(self, event)

    def leaveEvent(self, event):
        self.update()
        QtWidgets.QAbstractButton.leaveEvent(self, event)
