from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import QPointF
from PySide2.QtGui import QPaintEvent, QPainter, QPen, QColor, QBrush

from pcot.cameras.filters import wav2RGB


class SpectrumWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)  # Inherit from QWidget
        self.data = None  # None, or a list of (x,y) tuples
        self.text = None

    def map(self, x, y, asPoint=True, xoff=0, yoff=0):
        """map 0-1 in both coords to widget space"""
        topmargin, rightmargin, bottommargin, leftmargin = 4, 10, 30, 30
        width = self.width() - (leftmargin + rightmargin)
        height = self.height() - (topmargin + bottommargin)
        x = x * width + leftmargin + xoff
        y = (1 - y) * height + topmargin + yoff
        if asPoint:
            return QPointF(x, y)
        else:
            return x, y

    def set(self, data=None, text=""):
        """Takes iterable of (cwl,val,unc,dq) tuples AND a string. If the data is null, nothing is plotted"""
        self.text = text
        if data is not None:
            self.data = list(data)
            if len(self.data) == 0:
                self.data = None
            else:
                self.data.sort(key=lambda x: x[0])  # sort into wavelength order
        else:
            self.data = None
        self.repaint()

    def drawText(self, p, s):
        p.drawText(50, 10, self.width() - 10, self.height() - 10, QtCore.Qt.TextWordWrap, s)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.text is not None:
            self.drawText(p, self.text)
        if self.data is not None and len(self.data) > 0:
            # get x-range so we can check it (and use it later for rendering)
            xs = [x[0] for x in self.data]
            minx, maxx = min(xs), max(xs)
            rngx = maxx - minx

            # get Y range if it's not 0-1.
            ymax = 1
            for x, y, _, _ in self.data:
                while y > ymax:
                    ymax = y

            if rngx < 0.0001:
                text = f"There is only one single-wavelength\nchannel: wavelength {minx}nm"
                self.drawText(p, text)
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
            halftextheight = metrics.height() / 2
            for x, y, unc, _ in self.data:
                x01 = (x - minx) / rngx

                # draw x value on axis with a tick
                t = f"{x}"
                tw = metrics.width(t)
                p.drawText(self.map(x01, -0.05, xoff=-tw / 2), t)
                p.drawLine(self.map(x01, -0.01), self.map(x01, 0.01))

                # draw a 1 on the y-axis
                p.drawText(self.map(0, 1.0/ymax, xoff=-15, yoff=halftextheight), "1")
                p.drawLine(self.map(-0.01, 1.0/ymax), self.map(0.01, 1.0/ymax))

                pt = self.map(x01, y/ymax)  # point is scaled by ymax
                # draw y value next to point, offset down a little
                t = f"{y:.2f}"
                p.drawText(pt+QPointF(10, halftextheight), t)

                r, g, b = wav2RGB(x, scale=255.0)
                p.setBrush(QColor(r, g, b))
                p.drawEllipse(pt, 3, 3)
                p.setBrush(QBrush())

                # draw line between this and previous segment
                if lastPt is not None:
                    p.drawLine(pt, lastPt)
                lastPt = pt
                
                # draw error bar
                errorHalfHeight = unc/2
                
                pt1 = self.map(x01,(y+errorHalfHeight)/ymax)
                pt2 = self.map(x01,(y-errorHalfHeight)/ymax)
                p.drawLine(pt1,pt2)
