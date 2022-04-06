from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import pyqtSignal, QSize, QRect
from PyQt5.QtGui import QPaintEvent, QPainter, QColor
from PyQt5.QtCore import Qt


class TextToggleButton(QtWidgets.QWidget):
    """a simple toggling switch consisting of a string inside a box. Takes up less room than a
    checkbox."""
    toggled = pyqtSignal(bool)

    def __init__(self, textOn, textOff, initState=False, parent=None):
        QtWidgets.QWidget.__init__(self, parent)  # Inherit from QWidget

        self.textOn = textOn
        self.textOff = textOff
        self.margin = 5
        self.state = initState

        metrics = QtGui.QFontMetrics(self.font())
        s1 = metrics.size(Qt.TextShowMnemonic, textOn)
        s2 = metrics.size(Qt.TextShowMnemonic, textOff)
        s = s1 if s1.width() >= s2.width() else s2
        self.size = QSize(s.width() + self.margin * 2, s.height() + self.margin * 2)

    def sizeHint(self):
        return self.size

    def toggle(self):
        self.state = not self.state
        self.update()
        self.toggled.emit(self.state)

    def setChecked(self, s):
        self.state = s

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        self.toggle()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)

        r = QRect(0, 0, self.width() - 1, self.height() - 1)

        if self.isEnabled():
            crossOutCol = QColor(100, 100, 100)
            if self.state:
                boxOutline = QColor(0, 200, 0)
                boxFill = QColor(200, 255, 200)
                textCol = Qt.black
            else:
                boxOutline = QColor(100, 100, 100)
                boxFill = QColor(200, 200, 200)
                textCol = QColor(100, 100, 100)
        else:
            crossOutCol = QColor(160, 160, 160)
            if self.state:
                boxOutline = QColor(100, 200, 100)
                boxFill = QColor(200, 255, 200)
                textCol = QColor(100, 100, 100)
            else:
                boxOutline = QColor(200, 200, 200)
                boxFill = QColor(210, 210, 210)
                textCol = QColor(160, 160, 160)

        p.setPen(boxOutline)
        p.setBrush(boxFill)
        p.drawRoundedRect(r, self.margin, self.margin)

        t = self.textOn if self.state else self.textOff
        p.setPen(textCol)
        p.drawText(r, Qt.AlignCenter, t)

        if not self.state:
            p.setPen(crossOutCol)
            p.drawLine(r.topLeft(), r.bottomRight())

        p.end()