import cv2 as cv
import numpy as np
from PyQt5 import QtGui, QtCore

import pcot.conntypes as conntypes

from pcot.xform import xformtype, XFormType, XFormException, Datum
import pcot.ui.tabs
from pcot.pancamimage import ImageCube


@xformtype
class XformGrey(XFormType):
    """Converts an RGB image to greyscale."""

    def __init__(self):
        super().__init__("greyscale", "colour", "0.0.0")
        self.addInputConnector("", "img")
        self.addOutputConnector("", "img")

    def createTab(self, n, w):
        return TabGrey(n, w)

    def init(self, node):
        node.img = None
        node.useCVConversion = False

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is None:
            node.img = None
        else:
            # all sources in one channel
            sources = set.union(*img.sources)

            if node.useCVConversion:
                if img.channels != 3:
                    raise XFormException('DATA', "Image must be RGB for OpenCV greyscale conversion")
                node.img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY), node.mapping, [sources])
            else:
                # create a transformation matrix specifying that the output is a single channel which
                # is the mean of all the channels in the source

                mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
                out = cv.transform(img.img, mat)
                node.img = ImageCube(out, node.mapping, [sources])

        node.setOutput(0, Datum(conntypes.IMG, node.img))


class TabGrey(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgrey.ui')  # same UI as sink
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.greyBox.stateChanged.connect(self.stateChanged)
        # sync tab with node
        self.onNodeChanged()

    def stateChanged(self, _):
        self.node.useCVConversion = self.w.greyBox.isChecked()
        self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.display(self.node.img)
        self.w.greyBox.setCheckState(QtCore.Qt.Checked if self.node.useCVConversion else QtCore.Qt.Unchecked)
