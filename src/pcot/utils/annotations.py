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
                  col: Tuple[float] = (1, 1, 0),
                  basetop: bool = False,  # is the y-coord the top of the text?
                  bgcol: Optional[Tuple] = None,
                  fontsize=20):
    """Draw text for annotation. Coords must be in painter space."""
    p.setPen(rgb2qcol(col))
    annotFont.setPixelSize(fontsize)
    p.setFont(annotFont)
    metrics = QFontMetrics(annotFont)
    vmargin = metrics.height() * 0.1  # top-bottom margin as factor of height
    hmargin = metrics.height() * 0.1  # left-right margin as factor of height (not width)

    h = metrics.height() + vmargin * 2
    w = metrics.width(s) + hmargin * 2

    if not basetop:
        y = y + h

    if bgcol is not None:
        r = QRect(x, y - h, w, h)
        p.setBrush(rgb2qcol(bgcol))
        p.drawRect(r)

    # We need to do something with font weight!
    y -= metrics.descent() + vmargin
    p.drawText(QPoint(x + hmargin, y), s)


class Annotation:
    def __init__(self):
        self.inchesToUnits = 0  # gets set for annotatePDF.

    def minPDFMargins(self):
        """Annotations may require extra room in the margins of a PDF. This returns
        a tuple (top, right, bottom, left) of minimum margin sizes in inches."""
        return 0, 0, 0, 0

    def annotate(self, p: QPainter, img):
        """
        Draw the annotation
        Parameters:
        p: painter
        img: imagecube - we *may* scale the font and pen width up on larger images.
        """
        pass

    def annotatePDF(self, p: QPainter, img):
        """This method is called when we're annotating a PDF or PDF preview. It will be
        called IN ADDITION to annotate() but in a different coordinate system.
        It has the same parameters as annotate().
        When this is called, an extra member called inchesToUnits will be patched in so
        we can convert inches to the internal units.
        """
        pass
