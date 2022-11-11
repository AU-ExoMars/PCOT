import numpy as np
from PySide2.QtCore import QSizeF, QMarginsF
from PySide2.QtGui import QImage, QPainter, QPdfWriter

from pcot.imagecube import ImageCube


def exportPDF(imgcube, path):
    # a lot of this code will necessarily be similar to the paintEvent in InnerCanvas;
    # if there are commonalities I'll refactor them later.

    pdf = QPdfWriter(path)
    pdf.setPageMargins(QMarginsF(0, 0, 0, 0))  # see below about margins

    # this is the width of the PDF in inches excluding margins. We'll calculate the height from this.
    win = 10
    # this is the width of the PDF in our internal units - required because the drawing
    # functions actually take ints!
    w = ImageCube.PDFPixelWidth

    inchesToUnits = w / win

    # these are "pseudomargins" in inches; we can draw inside them so we aren't using
    # actual margins.

    marginTop = 0.2  # these are all minima
    marginBottom = 0.2
    marginLeft = 0.2
    marginRight = 0.2

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

    # set the page size to win x hin inches. Having bother with overloading here,
    # so doing it in mm.
    pdf.setPageSizeMM(QSizeF(win * 25.4, hin * 25.4))

    p = QPainter(pdf)

    p.setWindow(0, 0, int(w), int(h))  # set coordinate system

    # We can render arbitrary things in here, in "virtual units" space (i.e. width=10000).
    # We'll use this to put stuff in the margins.
    #        fontSize = inchesToUnits*0.3
    #        annotFont.setPixelSize(fontSize)    # ints!
    #        p.setFont(annotFont)
    #        p.drawText(0, int(marginTop*inchesToUnits), "FISHHEAD")

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

    # draw the annotations - this is the same method the canvas calls.
    imgcube.drawAnnotationsAndROIs(p, inPDF=False)

    # this removes the margin and puts us back into our coord space where w=10000
    p.restore()
    # and draw the annotations calling the annotatePDF methods this time.
    imgcube.drawAnnotationsAndROIs(p, inPDF=True)

    p.end()
