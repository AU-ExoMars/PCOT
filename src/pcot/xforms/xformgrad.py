from functools import partial
from typing import Tuple
import logging

import numpy as np
from PySide2.QtCore import Qt, QPoint, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QPen, QFontMetrics
from PySide2.QtWidgets import QInputDialog

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, taggedColourType, taggedRectType, Maybe
from pcot.rois import ROI
from pcot.sources import MultiBandSource
from pcot.utils.annotations import Annotation, annotFont, pixels2painter
from pcot.utils.colour import colDialog, rgb2qcol
from pcot.utils.gradient import Gradient
from pcot.xform import xformtype, XFormType, XFormException

logger = logging.getLogger(__name__)


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

    # the maps below are generated from the R "viridis" maps:
    # https://cran.r-project.org/web/packages/viridis/citation.html
    # Garnier, Simon, Ross, Noam, Rudis, Robert, Camargo, Pedro A, Sciaini, Marco, Scherer, Cédric (2021).
    # viridis - Colorblind-Friendly Color Maps for R.
    # doi:10.5281/zenodo.4679424

    "viridis": Gradient([
        (0.000000, (0.266667, 0.003922, 0.329412)),
        (0.111111, (0.282353, 0.156863, 0.470588)),
        (0.222222, (0.243137, 0.290196, 0.537255)),
        (0.333333, (0.192157, 0.407843, 0.556863)),
        (0.444444, (0.149020, 0.509804, 0.556863)),
        (0.555556, (0.121569, 0.619608, 0.537255)),
        (0.666667, (0.207843, 0.717647, 0.474510)),
        (0.777778, (0.427451, 0.803922, 0.349020)),
        (0.888889, (0.705882, 0.870588, 0.172549)),
        (1.000000, (0.992157, 0.905882, 0.145098))
    ]),

    "magma": Gradient([
        (0.000000, (0.000000, 0.000000, 0.015686)),
        (0.111111, (0.094118, 0.058824, 0.243137)),
        (0.222222, (0.270588, 0.062745, 0.466667)),
        (0.333333, (0.447059, 0.121569, 0.505882)),
        (0.444444, (0.623529, 0.184314, 0.498039)),
        (0.555556, (0.803922, 0.250980, 0.443137)),
        (0.666667, (0.945098, 0.376471, 0.364706)),
        (0.777778, (0.992157, 0.584314, 0.403922)),
        (0.888889, (0.996078, 0.788235, 0.552941)),
        (1.000000, (0.988235, 0.992157, 0.749020))
    ]),

    "plasma": Gradient([
        (0.000000, (0.050980, 0.031373, 0.529412)),
        (0.111111, (0.278431, 0.011765, 0.623529)),
        (0.222222, (0.450980, 0.003922, 0.658824)),
        (0.333333, (0.611765, 0.090196, 0.619608)),
        (0.444444, (0.741176, 0.215686, 0.525490)),
        (0.555556, (0.847059, 0.341176, 0.419608)),
        (0.666667, (0.929412, 0.474510, 0.325490)),
        (0.777778, (0.980392, 0.619608, 0.231373)),
        (0.888889, (0.992157, 0.788235, 0.149020)),
        (1.000000, (0.941176, 0.976471, 0.129412))
    ]),

    "inferno": Gradient([
        (0.000000, (0.000000, 0.000000, 0.015686)),
        (0.111111, (0.105882, 0.047059, 0.258824)),
        (0.222222, (0.294118, 0.047059, 0.419608)),
        (0.333333, (0.470588, 0.109804, 0.427451)),
        (0.444444, (0.647059, 0.172549, 0.376471)),
        (0.555556, (0.811765, 0.266667, 0.274510)),
        (0.666667, (0.929412, 0.411765, 0.145098)),
        (0.777778, (0.984314, 0.603922, 0.023529)),
        (0.888889, (0.968627, 0.815686, 0.235294)),
        (1.000000, (0.988235, 1.000000, 0.643137))
    ]),

    "cividis": Gradient([
        (0.000000, (0.000000, 0.125490, 0.301961)),
        (0.111111, (0.000000, 0.200000, 0.435294)),
        (0.222222, (0.223529, 0.282353, 0.419608)),
        (0.333333, (0.341176, 0.360784, 0.427451)),
        (0.444444, (0.439216, 0.443137, 0.450980)),
        (0.555556, (0.541176, 0.529412, 0.474510)),
        (0.666667, (0.650980, 0.615686, 0.458824)),
        (0.777778, (0.768627, 0.709804, 0.423529)),
        (0.888889, (0.894118, 0.811765, 0.356863)),
        (1.000000, (1.000000, 0.917647, 0.274510))
    ]),

    "mako": Gradient([
        (0.000000, (0.043137, 0.015686, 0.019608)),
        (0.111111, (0.156863, 0.098039, 0.184314)),
        (0.222222, (0.231373, 0.184314, 0.368627)),
        (0.333333, (0.250980, 0.286275, 0.556863)),
        (0.444444, (0.211765, 0.415686, 0.623529)),
        (0.555556, (0.203922, 0.541176, 0.650980)),
        (0.666667, (0.219608, 0.666667, 0.674510)),
        (0.777778, (0.329412, 0.788235, 0.678431)),
        (0.888889, (0.627451, 0.874510, 0.725490)),
        (1.000000, (0.870588, 0.960784, 0.898039))
    ]),

    "turbo": Gradient([
        (0.000000, (0.188235, 0.070588, 0.231373)),
        (0.111111, (0.274510, 0.384314, 0.843137)),
        (0.222222, (0.211765, 0.666667, 0.976471)),
        (0.333333, (0.101961, 0.894118, 0.713726)),
        (0.444444, (0.447059, 0.996078, 0.368627)),
        (0.555556, (0.780392, 0.937255, 0.203922)),
        (0.666667, (0.980392, 0.729412, 0.223529)),
        (0.777778, (0.964706, 0.419608, 0.098039)),
        (0.888889, (0.796078, 0.164706, 0.015686)),
        (1.000000, (0.478431, 0.015686, 0.011765))
    ]),

    "rocket": Gradient([
        (0.000000, (0.011765, 0.019608, 0.101961)),
        (0.111111, (0.164706, 0.086275, 0.211765)),
        (0.222222, (0.333333, 0.117647, 0.309804)),
        (0.333333, (0.517647, 0.117647, 0.352941)),
        (0.444444, (0.705882, 0.086275, 0.345098)),
        (0.555556, (0.866667, 0.172549, 0.270588)),
        (0.666667, (0.941176, 0.376471, 0.262745)),
        (0.777778, (0.960784, 0.576471, 0.415686)),
        (0.888889, (0.964706, 0.752941, 0.619608)),
        (1.000000, (0.980392, 0.921569, 0.866667))
    ])

}


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

    def _doAnnotate(self, p: QPainter, alpha, inPDF):
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
            col = rgb2qcol(colour)
        else:
            x, y, w, h = self.rect
            colour = self.colour
            vertical = self.vertical
            fontscale = self.fontscale
            borderThickness = self.thickness
            col = rgb2qcol(colour, alpha)
            barThickness = w

        p.fillRect(QRectF(x, y, w, h), self.grad.getGradient(vertical=vertical))
        p.setBrush(Qt.NoBrush)
        pen = QPen(col)
        pen.setWidth(borderThickness)
        p.setPen(pen)
        p.drawRect(int(x), int(y), int(w), int(h))

        annotFont.setPixelSize(pixels2painter(fontscale, p))
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

    def annotate(self, p: QPainter, img, alpha):
        if self.legendpos == IN_IMAGE:
            self._doAnnotate(p, alpha, False)


def _normAndGetRange(subimage):
    masked = np.ma.masked_array(subimage.img, mask=~subimage.fullmask())
    maxval = np.max(masked)
    minval = np.min(masked)
    if maxval == minval:
        raise XFormException('DATA', 'Data is uniform, cannot normalize for gradient')
    return minval, maxval, (masked - minval) / (maxval - minval)


TAGGEDDICT = TaggedDictType(
    # We only use this structure for serialisation and deserialisation - the actual gradient
    # is a Gradient object.
    gradient=('gradient', TaggedListType("gradient",
                                         TaggedDictType(
                                             x=('x', float, 0.0),
                                             colour=('colour', taggedColourType(0.0, 0.0, 0.0), None)
                                         ).setOrdered(), 0),
              None),
    # this is only really used when we use parameter files to set from presets.
    preset=('preset', Maybe(str), None, presetGradients.keys()),
    # other params are normal
    colour=('legend colour', taggedColourType(1.0, 1.0, 0.0), None),
    legendrect=('legend rectangle if in image', taggedRectType(0, 0, 100, 20), None),
    vertical=('is legend vertical?', bool, False),
    fontscale=('size of legend font', float, 10),
    thickness=('thickness of legend border', float, 1),
    legendPos=('legend location', str, IN_IMAGE,
               [LEFT_MARGIN, RIGHT_MARGIN, TOP_MARGIN, BOTTOM_MARGIN, IN_IMAGE, NONE]),
    normbackground=('normalise background', bool, False),
    sigfigs=('significant figures', int, 6),
)


@xformtype
class XformGradient(XFormType):
    """
    Convert a mono image to an RGB gradient image for better visibility. If the "insetinto" input has an
    image AND there is a valid ROI in the mono image, the image will be inset into the RGB of the insetinto image.
    NOTE: if you change the "insetinto" image's RGB mapping you may need to "run all" to see the the change reflected.

    **Ignores DQ and uncertainty**


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
        * 'In image', 'Top margin', 'Bottom margin', 'Left margin', 'Right margin', 'None'
        These are also defined as constants LEFT_MARGIN... IN_IMAGE (and None)
    """

    def __init__(self):
        super().__init__("gradient", "data", "0.0.0")
        self.addInputConnector("mono", Datum.IMG)
        self.addInputConnector("background", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.params = TAGGEDDICT

    def serialise(self, node):
        # clear the node parameter's gradient list
        node.params.gradient.clear()
        # and then add the gradient data to it
        for x, (r, g, b) in node.gradient.data:
            p = node.params.gradient.append_default()
            p.x = x
            p.colour.set(r, g, b)
        # just to make sure, we clear the "preset" field. This is only used when a parameter file
        # runs the node, and we don't want to save it.
        node.params.preset = None

        # we don't return anything because node.params represents our
        # data.
        return None

    def nodeDataFromParams(self, node):
        # We're ignoring the actual dict and building from the params structure that's already been processed
        # into the node.

        if node.params.preset is None:
            # no preset provided - the usual case - so build a gradient from the list in the
            # parameters.
            node.gradient.data = []
            # run through the elements in the TaggedList and add them to the gradient
            for x in node.params.gradient:
                node.gradient.data.append((x.x, x.colour))
        else:
            # a preset has been given from a parameter file (usually) so set node.gradient from that
            if node.params.preset in presetGradients:
                node.gradient = presetGradients[node.params.preset]
            else:
                raise XFormException('DATA', f"Unknown gradient preset {node.params.preset}")

    def createTab(self, n, w):
        return TabGradient(n, w)

    def init(self, node):
        node.gradient = presetGradients['viridis']
        node.minval = 0.0
        node.maxval = 1.0

    def perform(self, node):
        mono = node.getInput(0, Datum.IMG)
        rgb = node.getInput(1, Datum.IMG)

        node.minval = 0.0
        node.maxval = 1.0
        if mono is None and rgb is None:
            out = None
        elif mono is None:
            out = ImageCube(rgb.rgb(), node.mapping, sources=rgb.rgbSources())
        elif mono.channels != 1:
            raise XFormException('DATA', 'Gradient must be on greyscale images')
        elif rgb is None or len(mono.rois) == 0:
            # we're just outputting the mono image, or there are no ROIs
            subimage = mono.subimage()
            node.minval, node.maxval, subimage.img = _normAndGetRange(subimage)
            newsubimg = node.gradient.apply(subimage.img, subimage.mask)
            # Here we make an RGB image from the input image. We then slap the gradient
            # onto the ROI. We use the default channel mapping, and the same source on each channel.
            source = mono.sources.getSources()
            outimg = ImageCube(mono.rgb(), node.mapping, sources=MultiBandSource([source, source, source]))
            outimg.rois = mono.rois  # copy ROIs in so they are visible if desired
            out = outimg.modifyWithSub(subimage, newsubimg, keepMapping=True)
        else:
            # save the ROIs, because we're going to need them later
            monoROIs = mono.rois
            mono = mono.cropROI()  # crop to ROI, keeping that ROI (but cropped, which is why we keep it above)
            subimage = mono.subimage()
            node.minval, node.maxval, subimage.img = _normAndGetRange(subimage)
            newsubimg = node.gradient.apply(subimage.img, subimage.mask)
            source = mono.sources.getSources()
            # this time we get the RGB from the background input
            # and we need to normalise the rgb first
            rgb = rgb.rgb()
            if node.params.normbackground:
                mx = np.max(rgb)
                mn = np.min(rgb)
                rgb = (rgb - mn) / (mx - mn)

            outimg = ImageCube(rgb, node.mapping, sources=MultiBandSource([source, source, source]))
            outimg.rois = monoROIs  # copy ROIs in so they are visible if desired
            # we keep the same RGB mapping and this time we're modifying an image at the original size,
            # so we splice the old ROIs back in. This is pretty horrific; I hope it makes sense. Remember
            # that the gradient image - which we're splicing back in - has been cropped to its ROI which
            # has also been modified so its BB will start at the origin. We need to splice into the RGB image
            # at the correct point, so we're doing this...
            roiUnion = ROI.roiUnion(monoROIs)  # may return None if there is an unset ROI
            if roiUnion is not None:
                subimage.setROI(outimg, roiUnion)
            out = outimg.modifyWithSub(subimage, newsubimg, keepMapping=True)

        fs = "{:." + str(node.params.sigfigs) + "}"
        if out is not None:
            out.annotations.append(GradientLegend(node.gradient,
                                                  node.params.legendPos,
                                                  node.params.legendrect,
                                                  node.params.vertical,
                                                  node.params.colour,
                                                  node.params.fontscale,
                                                  node.params.thickness,
                                                  (fs.format(node.minval), fs.format(node.maxval))
                                                  ))

        node.setOutput(0, Datum(Datum.IMG, out))


removeSpaces = str.maketrans('', '', ' ')


class TabGradient(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgrad.ui')
        self.w.gradient.gradientChanged.connect(self.gradientChanged)
        self.w.loadPreset.pressed.connect(self.loadPreset)

        self.w.legendPos.currentTextChanged.connect(self.legendPosChanged)
        self.w.fontSpin.valueChanged.connect(self.fontChanged)
        for x in [self.w.xSpin, self.w.ySpin, self.w.wSpin, self.w.hSpin]:
            x.editingFinished.connect(self.rectChanged)
        self.w.thicknessSpin.valueChanged.connect(self.thicknessChanged)
        self.w.sigFigs.valueChanged.connect(self.sigFigsChanged)
        self.w.orientCombo.currentTextChanged.connect(self.orientChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.normCheck.toggled.connect(self.normChanged)

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
        self.node.params.legendPos = string
        self.changed()

    def normChanged(self, val):
        self.mark()
        self.node.params.normbackground = val
        self.changed()

    def fontChanged(self, val):
        self.mark()
        self.node.params.fontscale = val
        self.changed()

    def rectChanged(self):
        self.mark()
        self.node.params.legendrect.set(
            self.w.xSpin.value(),
            self.w.ySpin.value(),
            self.w.wSpin.value(),
            self.w.hSpin.value()
        )
        self.changed()

    def thicknessChanged(self, val):
        self.mark()
        self.node.params.thickness = val
        self.changed()

    def sigFigsChanged(self, val):
        self.mark()
        self.node.params.sigfigs = val
        self.changed()

    def orientChanged(self, val):
        self.mark()
        self.node.params.vertical = (val == 'Vertical')
        self.changed()

    def loadPreset(self):
        # show a dialog
        name, ok = QInputDialog.getItem(self.window, "Select a preset", "Preset", presetGradients.keys(),
                                        0, False)
        if ok and name in presetGradients:
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
            self.node.params.colour = col
            self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.gradient.setGradient(self.node.gradient.data)
        s = f"Min:{self.node.minval:.6g}\nMax:{self.node.maxval:.6g}"
        self.w.rangeLabel.setText(s)

        self.w.legendPos.setCurrentText(self.node.params.legendPos)
        self.w.fontSpin.setValue(self.node.params.fontscale)
        self.w.sigFigs.setValue(self.node.params.sigfigs)
        x, y, w, h = self.node.params.legendrect
        self.w.xSpin.setValue(x)
        self.w.ySpin.setValue(y)
        self.w.wSpin.setValue(w)
        self.w.hSpin.setValue(h)
        self.w.orientCombo.setCurrentText('Vertical' if self.node.params.vertical else 'Horizontal')
        r, g, b = [x * 255 for x in self.node.params.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

        img = self.node.getOutput(0)
        self.w.canvas.display(img)
        if img is not None:
            self.w.xSpin.setMaximum(img.w)
            self.w.ySpin.setMaximum(img.h)
            self.w.wSpin.setMaximum(img.w)
            self.w.hSpin.setMaximum(img.h)
