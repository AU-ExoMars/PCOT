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
    p.setFont(annotFont)
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

    def annotate(self, p: QPainter):
        """
        Draw the annotation
        Parameters:
        p: painter
        annotations: list of annotations
        """
        pass


class TestAnnotation(Annotation):
    def annotate(self, p: QPainter):
        p.setPen(Qt.yellow)
        p.setBrush(Qt.yellow)

        # inspections off because these should be float, but drawRect expects int.
        # noinspection PyTypeChecker
        p.drawRect(20, 20, 40, 40)

        # noinspection PyTypeChecker
        r = QRect(20, 10, 100, 10)
        p.drawText(r, Qt.AlignLeft | Qt.AlignBottom, "Hello World")
