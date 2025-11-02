from math import ceil

import numpy as np
from PySide2.QtCore import QSizeF, QMarginsF, Qt, QSize, QRect, QRectF
from PySide2.QtGui import QImage, QPainter, QPdfWriter, QColor
from PySide2.QtSvg import QSvgGenerator

EXPORT_UNIT_WIDTH = 10000.0  # size of an image and its borders in internal units.


def export(imgcube, prepfunction, annotations=True, margin=0.2):
    """A bit functional. The drawing process consists of a lot of prep which creates a QPainter drawing
    on some backing object - such as a QPdfWriter or a QImage. So here we calculate all the things necessary
    to do the drawing and to create that backing object, and call a 'prepfunction' to create said object and
    the painter to draw on it. We then do the drawing and return.

    The exporters therefore have to provide a prepfunction, call this function with it, and do any other work."""
    # this is the width of the PDF in inches excluding margins. We'll calculate the height from this.
    win = 10
    # this is the width of the PDF in our internal units - required because the drawing
    # functions actually take ints!
    w = EXPORT_UNIT_WIDTH

    inchesToUnits = w / win

    # these are "pseudomargins" in inches; we can draw inside them so we aren't using
    # actual margins.

    marginTop = margin  # these are all minima
    marginBottom = margin
    marginLeft = margin
    marginRight = margin

    # and then expand the margins if annotations require it
    for ann in imgcube.annotations + imgcube.rois:
        t, r, b, ll = ann.minPDFMargins()
        ann.inchesToUnits = inchesToUnits
        marginTop = max(t, marginTop)
        marginRight = max(r, marginRight)
        marginBottom = max(b, marginBottom)
        marginLeft = max(ll, marginLeft)

    imgAspect = imgcube.h / imgcube.w  # calculate aspect ratio of the image (not the PDF because margins!)

    wIMGin = win - (marginLeft + marginRight)  # calculate width of image in inches
    hIMGin = wIMGin * imgAspect  # calculate height of image in inches
    hin = hIMGin + marginTop + marginBottom  # calculate height of PDF in inches
    h = w * (hin / win)  # unit in our coordinate system (where width is 1000)

    p = prepfunction(win, hin)  # call the setup function for the export method, getting a painter

    # We can render arbitrary things in here, in "virtual units" space (i.e. width=10000).
    # We'll use this to put stuff in the margins.
    #        fontSize = inchesToUnits*0.3
    #        annotFont.setPixelSize(fontSize)    # ints!
    #        p.setFont(annotFont)
    #        p.drawText(0, int(marginTop*inchesToUnits), "FISHHEAD")

    p.setWindow(0, 0, int(w), int(h))  # set coordinate system
    p.save()  # we're about to transform into a space where we can draw on the image
    p.translate(marginLeft * inchesToUnits, marginTop * inchesToUnits)
    sx = wIMGin * inchesToUnits / imgcube.w
    sy = hIMGin * inchesToUnits / imgcube.h
    p.scale(sx, sy)

    img = imgcube.rgb()  # get numpy RGB image to draw

    # Convert and draw the image
    # again, see other comments about problems with QImage using preset data.
    # (https://bugreports.qt.io/browse/PYSIDE-1563)
    # We stash into a field to avoid this.

    imgcube.tmpimage = (img * 256).clip(max=255).astype(np.ubyte)
    height, width, channel = imgcube.tmpimage.shape
    assert channel == 3
    bytesPerLine = 3 * width
    qimg = QImage(imgcube.tmpimage.data, width, height,
                  bytesPerLine, QImage.Format_RGB888)
    p.drawImage(0, 0, qimg)
    imgcube.tmpimage = None

    if annotations:
        # draw the annotations - this is the same method the canvas calls.
        imgcube.drawAnnotationsAndROIs(p, inPDF=False)
        # this removes the margin and puts us back into our coord space where w=10000
        p.restore()
        # and draw the annotations calling the annotatePDF methods this time.
        imgcube.drawAnnotationsAndROIs(p, inPDF=True)


def exportPDF(imgcube, path, annotations=True):
    # have to create a PDF writer in the outer scope or things crash; it looks like QPainter
    # doesn't store a backreference, so when prepfunc exits, a QPdfWriter created inside
    # will go away.

    pdf = QPdfWriter(path)

    def prepfunc(win, hin):
        nonlocal pdf
        # create a PDF writer and set it to have no margins (we're handling margins ourselves)
        pdf.setPageMargins(QMarginsF(0, 0, 0, 0))
        # set the page size to win x hin inches. Having bother with overloading here,
        # so doing it in mm.
        pdf.setPageSizeMM(QSizeF(win * 25.4, hin * 25.4))
        return QPainter(pdf)

    export(imgcube, prepfunc, annotations)


def exportRaster(imgcube, path, pixelWidth, transparentBackground=False, annotations=True):
    """Export an image to a PNG, JPG, GIF, PBM, PPM, BMP... Gets the format from
    the extension (see https://doc.qt.io/qt-6/qimage.html#reading-and-writing-image-files)
    Params:
        imgcube: the imagecube (current rgb mapping will be used)
        path: the filename, extension must be a supported type
        pixelWidth: the width in pixels
        transparentbackground: in the case of PNGs, will use an alpha=0 rather than white background"""

    outputImage = None   # see note on exportPDF

    if pixelWidth is None or pixelWidth < 0:
        pixelWidth = imgcube.w

    def prepfunc(win, hin):
        # now calculate image size. That's THREE coordinate systems: pixels, nominal "inches", and "units" (required because
        # too many things take ints so we can't use inches)

        pixelHeight = round(pixelWidth * (hin / win))

        # create an image in memory - 32bit ARGB if we need a transparent background, 24bit RGB if we don't
        nonlocal outputImage
        outputImage = QImage(pixelWidth, pixelHeight,
                             QImage.Format_ARGB32 if transparentBackground else QImage.Format_RGB888)
        # if we don't want a transparent background, fill with white
        if not transparentBackground:
            outputImage.fill(Qt.white)
        # and now paint on it.
        return QPainter(outputImage)

    export(imgcube, prepfunc, annotations, margin=0)

    # and save the image. Ignore the error here; outputImage is a reference to
    # None but that changes in the callback.
    outputImage.save(path)


def exportSVG(imgcube, path, annotations=True):
    svg = QSvgGenerator()
    svg.setFileName(path)

    def prepfunc(win, hin):
        nonlocal svg
        # sizes in svg are weird, and setSize requires ints. This will do. The roundup
        # of h stops bleeding.
        w = int(200 / 0.254)
        h = ceil(w * (hin / win))
        svg.setResolution(100)
        svg.setSize(QSize(w, h))
        svg.setViewBox(QRect(0, 0, w, h))
        return QPainter(svg)

    export(imgcube, prepfunc, annotations)
