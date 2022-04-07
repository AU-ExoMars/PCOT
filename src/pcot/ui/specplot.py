from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QPointF, QPoint
from PyQt5.QtGui import QPaintEvent, QPainter, QPen, QColor, QBrush

from pcot import ui
from pcot.filters import wav2RGB


class SpecPlot(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)  # Inherit from QWidget
        self.data = None  # None, or a string, or a list of (x,y) tuples

    def map(self, x, y, asPoint=True, xoff=0, yoff=0):
        topmargin, rightmargin, bottommargin, leftmargin = 4, 10, 30, 30
        width = self.width() - (leftmargin + rightmargin)
        height = self.height() - (topmargin + bottommargin)
        """map 0-1 in both coords to widget space"""
        x = x * width + leftmargin + xoff
        y = (1 - y) * height + topmargin + yoff
        if asPoint:
            return QPointF(x, y)
        else:
            return x, y


    def setData(self, d):
        """Takes iterable of (x,y) tuples OR a string"""
        if isinstance(d, str):
            self.data = d
        else:
            self.data = list(d)
            if len(self.data) == 0:
                self.data = "There are no single-wavelength\nchannels in the data"
            else:
                self.data.sort(key=lambda x: x[0])  # sort into wavelength order
        self.repaint()

    def drawText(self, p, s):
        p.drawText(10, 10, self.width() - 10, self.height() - 10, QtCore.Qt.TextWordWrap, s)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if isinstance(self.data, str):
            self.drawText(p, self.data)
        elif self.data is not None and len(self.data) > 0:
            # get x-range so we can check it (and use it later for rendering)
            xs = [x for x, _ in self.data]
            minx, maxx = min(xs), max(xs)
            rngx = maxx - minx

            if rngx < 0.0001:
                self.drawText(p, "There is only one single-wavelength\nchannel in the data")
                return

            # draw axes

            p.drawLine(self.map(0, 0), self.map(1, 0))
            p.drawLine(self.map(0, 0), self.map(0, 1))

            pen = QPen()
            pen.setWidth(10)
            p.setPen(pen)
            p.drawPoint(self.map(1, 0))
            p.drawPoint(self.map(0, 1))
            p.setPen(QPen())

            metrics = self.fontMetrics()

            lastPt = None
            for x, y in self.data:
                x01 = (x - minx) / rngx

                t = f"{x}"
                tw = metrics.width(t)
                p.drawText(self.map(x01, -0.05, xoff=-tw / 2), t)
                p.drawLine(self.map(x01, -0.01), self.map(x01, 0.01))

                pt = self.map(x01, y)

                r, g, b = wav2RGB(x, scale=255.0)
                p.setBrush(QColor(r, g, b))
                p.drawEllipse(pt, 3, 3)
                p.setBrush(QBrush())

                if lastPt is not None:
                    p.drawLine(pt, lastPt)
                lastPt = pt
