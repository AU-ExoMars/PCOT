from PySide2.QtCore import Qt, QRect, QPoint
from PySide2.QtGui import QPainter, QFont, QFontMetrics
from typing import Callable, Tuple, Optional

# use this font for annotations
from pcot.utils.colour import rgb2qcol

annotFont = QFont()
annotFont.setFamily('Sans Serif')


def annotDrawText(p: QPainter,
                  x, y, s,
                  col: Tuple[float] = (1,1,0),
                  basetop: bool=False,   # is the y-coord the top of the text?
                  bgcol: Optional[Tuple]=None,
                  fontsize=20):
    """Draw text for annotation. Coords must be in painter space."""
    p.setPen(rgb2qcol(col))
    annotFont.setPixelSize(fontsize)
    metrics = QFontMetrics(annotFont)
    h = metrics.height()
    w = metrics.width(s)
    if basetop:     # if the y-coord is the top of the text...
        y = y + fontsize
    else:
        y = y-metrics.descent()

    if bgcol is not None:
        r = QRect(x, y-fontsize, w, h)
        p.setBrush(rgb2qcol(bgcol))
        p.drawRect(r)

    # We need to do something with font weight!
    p.drawText(QPoint(x, y), s)


class Annotation:
    def __init__(self):
        pass

    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """
        Draw the annotation
        Parameters:
        p: painter
        annotations: list of annotations
        scale: scaling factor from img to painter (for sizes)
        mapcoords: function to map coords from img to painter - takes x,y; yields (x,y) tuple

        See TestAnnotation for an example.
        """
        pass


class TestAnnotation(Annotation):
    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        p.setPen(Qt.yellow)
        p.setBrush(Qt.yellow)

        # now for the important bit...

        # DIVIDE by scale to get canvas width/heights
        # use mapcoords to get canvas coords.

        cx, cy = mapcoords(20, 20)

        # inspections off because these should be float, but drawRect expects int.
        # noinspection PyTypeChecker
        p.drawRect(cx, cy, 40 / scale, 40 / scale)

        cx, cy = mapcoords(20, 10)
        # noinspection PyTypeChecker
        r = QRect(cx, cy, 100 / scale, 10 / scale)
        p.drawText(r, Qt.AlignLeft | Qt.AlignBottom, "Hello World")
