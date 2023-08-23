from PySide2.QtCore import Qt, QRect, QPoint, QPointF
from PySide2.QtGui import QPainter, QFont, QFontMetrics, QPen
from typing import Callable, Tuple, Optional

# use this font for annotations
from pcot import ui
from pcot.utils.colour import rgb2qcol

annotFont = QFont()
annotFont.setFamily('Sans Serif')


def pixels2painter(v, p: QPainter):
    """Given a size value in pixels, get what the painter size should be (i.e. take account of scaling)"""
    sc = p.worldTransform().m11()
    return v/sc


def annotDrawText(p: QPainter,
                  x, y, s,
                  col: Tuple[float] = (1, 1, 0),
                  basetop: bool = False,  # is the y-coord the top of the text?
                  bgcol: Optional[Tuple] = None,
                  fontsize=15):
    """Draw text for annotation. Coords must be in painter space."""
    pen = QPen(rgb2qcol(col))
    pen.setWidth(0)
    p.setPen(pen)

    annotFont.setPixelSize(pixels2painter(fontsize*2, p))
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


class IndexedPointAnnotation(Annotation):
    """An annotation of a single point with an index and colour, which may or may
    not be selected. These may a radius, because the crosscalib node has a radius over which
    it collects values. If not they always show as the same radius."""
    def __init__(self, idx, x, y, issel, col, radius=None):
        self.col = col
        self.x = x
        self.y = y
        self.r = radius
        self.issel = issel
        self.idx = idx

    def annotate(self, p: QPainter, img):
        pen = QPen(self.col)
        pen.setWidth(0)  # "cosmetic" pen with width 0
        p.setPen(pen)

        x = self.x + 0.5
        y = self.y + 0.5

        r = self.r
        if r is None:
            r = pixels2painter(5, p)

        p.drawEllipse(QPointF(x, y), r, r)
        if self.issel:
            # we draw the selected point with an extra circle INSIDE.
            p.drawEllipse(QPointF(x, y), 0.7*r, 0.7*r)

        fontsize = 15   # font size in on-screen pixels
        annotFont.setPixelSize(pixels2painter(fontsize, p))
        p.setFont(annotFont)
        p.drawText(x+r*2, y+r*2, f"{self.idx}")