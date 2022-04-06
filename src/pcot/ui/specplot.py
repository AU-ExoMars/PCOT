from PyQt5 import QtWidgets
from PyQt5.QtCore import QPointF, QPoint
from PyQt5.QtGui import QPaintEvent, QPainter, QPen, QColor, QBrush

from pcot import ui
from pcot.filters import wav2RGB


class SpecPlot(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)  # Inherit from QWidget
        self.data = None

    def map(self, x, y, asPoint=True, xoff=0, yoff=0):
        topmargin, rightmargin, bottommargin, leftmargin = 4, 10, 30, 30
        width = self.width() - (leftmargin+rightmargin)
        height = self.height() - (topmargin+bottommargin)
        """map 0-1 in both coords to widget space"""
        x = x * width + leftmargin + xoff
        y = (1 - y) * height + topmargin + yoff
        if asPoint:
            return QPointF(x, y)
        else:
            return x, y

    def setData(self, d):
        """Takes iterable of (x,y) tuples"""
        self.data = list(d)
        self.data.sort(key=lambda x: x[0])  # sort into wavelength order
        self.repaint()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.data is not None and len(self.data) > 0:
            # draw axes
            p.drawLine(self.map(0, 0), self.map(1, 0))
            p.drawLine(self.map(0, 0), self.map(0, 1))

            pen = QPen()
            pen.setWidth(10)
            p.setPen(pen)
            p.drawPoint(self.map(1,0))
            p.drawPoint(self.map(0,1))
            p.setPen(QPen())

            xs = [x for x, _ in self.data]
            minx, maxx = min(xs), max(xs)
            rngx = maxx-minx
            metrics = self.fontMetrics()

            lastPt = None
            for x, y in self.data:
                x01 = (x-minx)/rngx

                t = f"{x}"
                tw = metrics.width(t)
                p.drawText(self.map(x01, -0.05, xoff=-tw/2), t)
                p.drawLine(self.map(x01, -0.01), self.map(x01, 0.01))

                pt = self.map(x01, y)

                r,g,b = wav2RGB(x, scale=255.0)
                p.setBrush(QColor(r,g,b))
                p.drawEllipse(pt, 3, 3)
                p.setBrush(QBrush())

                if lastPt is not None:
                    p.drawLine(pt, lastPt)
                lastPt = pt