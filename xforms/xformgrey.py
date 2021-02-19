import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas

from xform import xformtype, XFormType
from xforms.tabimage import TabImage
from pancamimage import ImageCube


@xformtype
class XformGrey(XFormType):
    """Converts an RGB image to greyscale."""

    def __init__(self):
        super().__init__("greyscale", "colour", "0.0.0")
        self.addInputConnector("", "imgrgb")
        self.addOutputConnector("", "imggrey")

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            print(img.img.shape, img.img.dtype)
            if img.channels != 3:
                raise Exception("Image must be RGB for greyscale conversion")
            # all the sources get merged - all three channels' sources appear in all the output channels
            sources = set.union(img.sources[0], img.sources[1], img.sources[2])
            node.img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY),
                                 node.mapping,
                                 [sources, sources, sources])

        node.setOutput(0, node.img)
