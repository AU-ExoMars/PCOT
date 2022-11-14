from functools import partial
from typing import Tuple

import numpy as np
from PySide2.QtCore import Qt, QPoint, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QPen, QFontMetrics

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.rois import ROI
from pcot.sources import MultiBandSource
from pcot.utils.annotations import Annotation, annotFont
from pcot.utils.colour import colDialog, rgb2qcol
from pcot.utils.gradient import Gradient
from pcot.xform import xformtype, XFormType, XFormException

LEFT_MARGIN = "Left margin"
RIGHT_MARGIN = "Right margin"
TOP_MARGIN = "Top margin"
BOTTOM_MARGIN = "Bottom margin"
IN_IMAGE = "In image"
NONE = "None"

presetGradients = {
    "topo": Gradient([
        (0.000000, (0.298039, 0.000000, 1.000000)),
        (0.111111, (0.000000, 0.098039, 1.000000)),
        (0.222222, (0.000000, 0.501961, 1.000000)),
        (0.333333, (0.000000, 0.898039, 1.000000)),
        (0.444444, (0.000000, 1.000000, 0.301961)),
        (0.555556, (0.301961, 1.000000, 0.000000)),
        (0.666667, (0.901961, 1.000000, 0.000000)),
        (0.777778, (1.000000, 1.000000, 0.000000)),
        (0.888889, (1.000000, 0.870588, 0.349020)),
        (1.000000, (1.000000, 0.000000, 0.000000)),
    ]),

    "grey": Gradient([
        (0, (0, 0, 0)),
        (1, (1, 1, 1)),
    ]),
}


def sigfigs(val: float, n: int):
    return '{:g}'.format(float('{:.{p}g}'.format(val, p=n)))


class GradientLegend(Annotation):
    grad: QLinearGradient
    mn: float
    mx: float
    fontsize: float

    def __init__(self, grad: Gradient,
                 legendpos: str,
                 legendrect: Tuple[float, float, float, float],
                 vertical: bool,
                 colour: Tuple[float, float, float],
                 fontscale: float,
                 thickness: float,
                 rangestrs: Tuple[str, str]):
        super().__init__()
        self.legendpos = legendpos
        self.colour = colour
        self.fontscale = fontscale
        self.rect = legendrect
        self.thickness = thickness
        self.vertical = vertical
        self.grad = grad
        self.rangestrs = rangestrs

    def minPDFMargins(self):
        if self.legendpos == TOP_MARGIN:
            return 1, 0, 0, 0
        elif self.legendpos == BOTTOM_MARGIN:
            return 0, 0, 1, 0
        elif self.legendpos == LEFT_MARGIN:
            return 0, 0, 0, 1
        elif self.legendpos == RIGHT_MARGIN:
            return 0, 1, 0, 0
        else:
            return 0, 0, 0, 0

    def _doAnnotate(self, p: QPainter, inPDF):
        """Core annotation method"""
        # if we're doing a margin annotation we override many of the values passed in
        i2u = self.inchesToUnits
        heightUnits = p.window().height()
        textGap = 0

        if inPDF:
            textGap = i2u * 0.1  # gap between text and bar
            fontscale = i2u * 0.2
            barThickness = i2u * 0.3
            borderThickness = 10
            colour = (0, 0, 0)

            if self.legendpos == TOP_MARGIN:
                vertical = False
                x, y, w, h = (2000, i2u * 0.3, 6000, barThickness)
            elif self.legendpos == BOTTOM_MARGIN:
                vertical = False
                x, y, w, h = (2000, heightUnits - i2u * 0.66, 6000, barThickness)
            elif self.legendpos == LEFT_MARGIN:
                vertical = True
                x, y, w, h = (i2u * 0.5 - barThickness / 2,
                              i2u * 0.2 + fontscale + textGap,
                              barThickness,
                              heightUnits -  # height of image
                              i2u * 0.4 -  # -2*margin
                              (fontscale + textGap) * 2)  # -font size and a little bit
            elif self.legendpos == RIGHT_MARGIN:
                vertical = True
                x, y, w, h = (10000 - (i2u * 0.5 + barThickness / 2),
                              i2u * 0.2 + fontscale + textGap,
                              barThickness,
                              heightUnits -  # height of image
                              i2u * 0.4 -  # -2*margin
                              (fontscale + textGap) * 2)  # -font size and a little bit
            else:
                raise XFormException('DATA', 'Bad margin placement option')
        else:
            x, y, w, h = self.rect
            colour = self.colour
            vertical = self.vertical
            fontscale = self.fontscale
            borderThickness = self.thickness
            barThickness = w

        p.fillRect(QRectF(x, y, w, h), self.grad.getGradient(vertical=vertical))
        p.setBrush(Qt.NoBrush)
        pen = QPen(rgb2qcol(colour))
        pen.setWidth(borderThickness)
        p.setPen(pen)
        p.drawRect(int(x), int(y), int(w), int(h))

        annotFont.setPixelSize(fontscale)
        p.setFont(annotFont)
        metrics = QFontMetrics(annotFont)

        mintext, maxtext = self.rangestrs
        minw = metrics.width(mintext)
        maxw = metrics.width(maxtext)
        if vertical:
            xt = x - (self.thickness + 2) + barThickness / 2

            p.drawText(QPoint(xt - minw / 2, int(y + h + fontscale + textGap)), f"{mintext}")
            p.drawText(QPoint(xt - maxw / 2, int(y - textGap)), f"{maxtext}")
        else:
            p.drawText(QPoint(x - minw / 2, int(y - self.fontscale + 2)), f"{mintext}")
            p.drawText(QPoint((x + w) - maxw / 2, int(y - self.fontscale + 2)), f"{maxtext}")

    def annotatePDF(self, p: QPainter, img):
        if self.legendpos != IN_IMAGE and self.legendpos != NONE and self.legendpos is not None:
            self._doAnnotate(p, True)

    def annotate(self, p: QPainter, img):
        if self.legendpos == IN_IMAGE:
            self._doAnnotate(p, False)


def _normAndGetRange(subimage):
    masked = np.ma.masked_array(subimage.img, mask=~subimage.fullmask())
    maxval = np.max(masked)
    minval = np.min(masked)
    if maxval == minval:
        raise XFormException('DATA', 'Data is uniform, cannot normalize for gradient')
    return minval, maxval, (masked - minval) / (maxval - minval)


@xformtype
class XformGradient(XFormType):
    """
    Convert a mono image to an RGB gradient image for better visibility. If the "insetinto" input has an
    image AND there is a valid ROI in the mono image, the image will be inset into the RGB of the insetinto image.
    NOTE: if you change the "insetinto" image's RGB mapping you may need to "run all" to see the the change reflected.

    The gradient widget has the following behaviour:

        * click and drag to move a colour point
        * doubleclick to delete an existing colour point
        * doubleclick to add a new colour point
        * right click to edit an existing colour point

    Node parameters:
        * gradient: utils.Gradient object containing gradient info
        * colour: (r,g,b) [0:1] colour of text and border for in-image legend
        * legendrect: (x,y,w,h) rectangle for in-image legend
        * vertical: true if vertical legend
        * fontscale: size of font
        * thickness: border thickness
        * legendPos: string describing position:
            'In image', 'Top margin', 'Bottom margin', 'Left margin', 'Right margin', 'None'
            These are also defined as constants LEFT_MARGIN... IN_IMAGE (and None)
    """

    def __init__(self):
        super().__init__("gradient", "data", "0.0.0")
        self.addInputConnector("mono", Datum.IMG)
        self.addInputConnector("insetinto", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.hasEnable = True
        self.autoserialise = ('colour', 'legendrect', 'vertical', 'thickness', 'fontscale', 'legendPos')

    def serialise(self, node):
        return {'gradient': node.gradient.data}

    def deserialise(self, node, d):
        node.gradient = Gradient(d['gradient'])

    def createTab(self, n, w):
        return TabGradient(n, w)

    def init(self, node):
        node.img = None
        node.gradient = presetGradients['topo']
        node.colour = (1, 1, 0)
        node.legendrect = (0, 0, 100, 20)
        node.vertical = False
        node.fontscale = 10
        node.thickness = 1
        node.legendPos = IN_IMAGE

    def perform(self, node):
        mono = node.getInput(0, Datum.IMG)
        rgb = node.getInput(1, Datum.IMG)

        if not node.enabled:
            return

        if mono is None and rgb is None:
            node.img = None
        elif mono is None:
            node.img = ImageCube(rgb.rgb(), node.mapping, sources=rgb.rgbSources())
            minval = 0
            maxval = 1
        elif mono.channels != 1:
            raise XFormException('DATA', 'Gradient must be on greyscale images')
        elif rgb is None or len(mono.rois) == 0:
            # we're just outputting the mono image, or there are no ROIs
            subimage = mono.subimage()
            minval, maxval, subimage.img = _normAndGetRange(subimage)
            newsubimg = node.gradient.apply(subimage.img, subimage.mask)
            # Here we make an RGB image from the input image. We then slap the gradient
            # onto the ROI. We use the default channel mapping, and the same source on each channel.
            source = mono.sources.getSources()
            outimg = ImageCube(mono.rgb(), node.mapping, sources=MultiBandSource([source, source, source]))
            outimg.rois = mono.rois  # copy ROIs in so they are visible if desired
            node.img = outimg.modifyWithSub(subimage, newsubimg, keepMapping=True)
        else:
            # save the ROIs, because we're going to need them later
            monoROIs = mono.rois
            mono = mono.cropROI()  # crop to ROI, keeping that ROI (but cropped, which is why we keep it above)
            subimage = mono.subimage()
            minval, maxval, subimage.img = _normAndGetRange(subimage)
            newsubimg = node.gradient.apply(subimage.img, subimage.mask)
            source = mono.sources.getSources()
            # this time we get the RGB from the rgb input
            outimg = ImageCube(rgb.rgb(), node.mapping, sources=MultiBandSource([source, source, source]))
            outimg.rois = monoROIs  # copy ROIs in so they are visible if desired
            # we keep the same RGB mapping and this time we're modifying an image at the original size,
            # so we splice the old ROIs back in. This is pretty horrific; I hope it makes sense. Remember
            # that the gradient image - which we're splicing back in - has been cropped to its ROI which
            # has also been modified so its BB will start at the origin. We need to splice into the RGB image
            # at the correct point, so we're doing this...
            roiUnion = ROI.roiUnion(monoROIs)  # may return None if there is an unset ROI
            if roiUnion is not None:
                subimage.setROI(outimg, roiUnion)
            node.img = outimg.modifyWithSub(subimage, newsubimg, keepMapping=True)

        if node.img is not None:
            node.img.annotations.append(GradientLegend(node.gradient,
                                                       node.legendPos,
                                                       node.legendrect,
                                                       node.vertical,
                                                       node.colour,
                                                       node.fontscale,
                                                       node.thickness,
                                                       (f"{sigfigs(minval, 3)}", f"{sigfigs(maxval, 3)}")
                                                       ))

        node.setOutput(0, Datum(Datum.IMG, node.img))


removeSpaces = str.maketrans('', '', ' ')


class TabGradient(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgrad.ui')
        self.w.gradient.gradientChanged.connect(self.gradientChanged)
        for n in presetGradients:
            self.w.presetCombo.insertItem(1000, n)
        self.w.presetCombo.currentIndexChanged.connect(self.loadPreset)

        self.w.legendPos.currentTextChanged.connect(self.legendPosChanged)
        self.w.fontSpin.valueChanged.connect(self.fontChanged)
        for x in [self.w.xSpin, self.w.ySpin, self.w.wSpin, self.w.hSpin]:
            x.editingFinished.connect(self.rectChanged)
        self.w.thicknessSpin.valueChanged.connect(self.thicknessChanged)
        self.w.orientCombo.currentTextChanged.connect(self.orientChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)

        self.pageButtons = [
            self.w.gradPageButton,
            self.w.legendPageButton
        ]
        for x in self.pageButtons:
            # late binding closure hack.
            x.clicked.connect(partial(lambda xx: self.pageButtonClicked(xx), x))

        self.setPage(0)
        self.nodeChanged()

    def setPage(self, i):
        """Select page in the stacked widget"""
        self.w.stackedWidget.setCurrentIndex(i)
        for idx, x in enumerate(self.pageButtons):
            x.setChecked(i == idx)

    def pageButtonClicked(self, x):
        i = self.pageButtons.index(x)
        self.setPage(i)

    def legendPosChanged(self, string):
        self.mark()
        self.node.legendPos = string
        self.changed()

    def fontChanged(self, val):
        self.mark()
        self.node.fontscale = val
        self.changed()

    def rectChanged(self):
        self.mark()
        self.node.legendrect = [
            self.w.xSpin.value(),
            self.w.ySpin.value(),
            self.w.wSpin.value(),
            self.w.hSpin.value()
        ]
        self.changed()

    def thicknessChanged(self, val):
        self.mark()
        self.node.thickness = val
        self.changed()

    def orientChanged(self, val):
        self.mark()
        self.node.vertical = (val == 'Vertical')
        self.changed()

    def loadPreset(self):
        name = self.w.presetCombo.currentText()
        if name in presetGradients:
            # get a copy of the preset's data
            d = presetGradients[name].data.copy()
            # set the gradient to use that and update
            self.w.gradient.setGradient(d)
            self.w.gradient.update()
            self.mark()
            # set the node's gradient object to use that data
            # which will be modified by the widget
            self.node.gradient.setData(self.w.gradient.gradient())
            self.changed()

    def gradientChanged(self):
        self.mark()
        self.node.gradient.setData(self.w.gradient.gradient())
        self.changed()

    def colourPressed(self):
        col = colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.colour = col
            self.changed()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.gradient.setGradient(self.node.gradient.data)
        self.w.canvas.display(self.node.img)

        self.w.legendPos.setCurrentText(self.node.legendPos)
        self.w.fontSpin.setValue(self.node.fontscale)
        x, y, w, h = self.node.legendrect
        self.w.xSpin.setValue(x)
        self.w.ySpin.setValue(y)
        self.w.wSpin.setValue(w)
        self.w.hSpin.setValue(h)
        self.w.orientCombo.setCurrentText('Vertical' if self.node.vertical else 'Horizontal')
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

        if self.node.img is not None:
            self.w.xSpin.setMaximum(self.node.img.w)
            self.w.ySpin.setMaximum(self.node.img.h)
            self.w.wSpin.setMaximum(self.node.img.w)
            self.w.hSpin.setMaximum(self.node.img.h)
