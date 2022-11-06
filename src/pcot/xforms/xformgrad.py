import cv2 as cv
import numpy as np

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource
from pcot.utils.gradient import Gradient
from pcot.xform import xformtype, XFormType, XFormException

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


@xformtype
class XformGradient(XFormType):
    """
    Convert a greyscale image to an RGB gradient image for better visibility.

    The gradient widget has the following behaviour:

        * click and drag to move a colour point
        * doubleclick to delete an existing colour point
        * doubleclick to add a new colour point
        * right click to edit an existing colour point
    """

    def __init__(self):
        super().__init__("gradient", "data", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.hasEnable = True

    def serialise(self, node):
        return {'gradient': node.gradient.data}

    def deserialise(self, node, d):
        node.gradient = Gradient(d['gradient'])

    def createTab(self, n, w):
        return TabGradient(n, w)

    def init(self, node):
        node.gradient = presetGradients['topo']
        node.img = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            node.img = None
        elif node.enabled:
            if img.channels == 1:
                subimage = img.subimage()
                newsubimg = node.gradient.apply(subimage.img, subimage.mask)
                # Here we make an RGB image from the input image. We then slap the gradient
                # onto the ROI. We use the default channel mapping, and the same source on each channel.
                source = img.sources.getSources()
                outimg = ImageCube(img.rgb(), node.mapping, sources=MultiBandSource([source, source, source]))
                outimg.rois = img.rois  # copy ROIs in so they are visible if desired

                # we keep the same RGB mapping
                node.img = outimg.modifyWithSub(subimage, newsubimg, keepMapping=True)
                snark = node.gradient.getImage(True)
            else:
                raise XFormException('DATA', 'Gradient must be on greyscale images')
        else:
            node.img = img
        node.setOutput(0, Datum(Datum.IMG, node.img))


class TabGradient(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgrad.ui')
        self.w.gradient.gradientChanged.connect(self.gradientChanged)
        for n in presetGradients:
            self.w.presetCombo.insertItem(1000, n)
        self.w.presetCombo.currentIndexChanged.connect(self.loadPreset)
        self.nodeChanged()

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

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.gradient.setGradient(self.node.gradient.data)
        self.w.canvas.display(self.node.img)

    def gradientChanged(self):
        self.mark()
        self.node.gradient.setData(self.w.gradient.gradient())
        self.changed()
