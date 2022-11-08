from PySide2.QtCore import Qt, QRect, QPoint
from PySide2.QtGui import QPainter, QFont, QFontMetrics
from typing import Callable, Tuple, Optional

# use this font for annotations
from pcot import ui
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
    vmargin = metrics.height() * 0.1     # top-bottom margin as factor of height
    hmargin = metrics.height() * 0.1     # left-right margin as factor of height (not width)

    h = metrics.height()+vmargin*2
    w = metrics.width(s)+hmargin*2

    if not basetop:
        y = y + h

    if bgcol is not None:
        r = QRect(x, y-h, w, h)
        p.setBrush(rgb2qcol(bgcol))
        p.drawRect(r)

    # We need to do something with font weight!
    y -= metrics.descent()+vmargin
    p.drawText(QPoint(x+hmargin, y), s)


class Annotation:
    def __init__(self):
        pass

    def annotate(self, p: QPainter, img, inPDF: bool):
        """
        Draw the annotation
        Parameters:
        p: painter
        img: imagecube - we *may* scale the font and pen width up on larger images.
        inPDF: true if we're drawing to a PDF or some other canvas with margins etc.
        """
        pass
