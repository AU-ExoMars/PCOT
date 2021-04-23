import cv2 as cv
import numpy as np

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot.xform import xformtype, XFormType, Datum
from pcot.pancamimage import ImageCube, ROIRect, ChannelMapping


@xformtype
class XformSplit(XFormType):
    """Splits an RGB image into three greyscale images"""

    def __init__(self):
        super().__init__("split", "colour", "0.0.0")
        ## our connectors
        self.addInputConnector("rgb", "imgrgb")
        self.addOutputConnector("r", "imggrey")
        self.addOutputConnector("g", "imggrey")
        self.addOutputConnector("b", "imggrey")

    def createTab(self, n, w):
        return TabSplit(n, w)


    def init(self, node):
        node.red = None
        node.green = None
        node.blue = None
        # the green channel uses the "default" mapping that the XForm has built in.
        # We have to add two more mappings for the other two canvases. They'll always
        # be single-channel, so we don't need to worry about serialisation.
        node.mappingR = ChannelMapping()
        node.mappingB = ChannelMapping()

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is not None and img.channels == 3:
            # image MUST have three sources - the input type should insure this,
            # because we only accept RGB
            # TODO this won't work with images which aren't RGB; of course split is going away soon.
            r, g, b = cv.split(img.img)  # kind of pointless on a greyscale..
            # We don't specify mappings here, it's pointless - they're single channel
            node.red = ImageCube(r, None, [img.sources[0]])
            node.green = ImageCube(g, None, [img.sources[1]])
            node.blue = ImageCube(b, None, [img.sources[2]])
            node.setOutput(0, Datum(conntypes.IMG,node.red))
            node.setOutput(1, Datum(conntypes.IMG,node.green))
            node.setOutput(2, Datum(conntypes.IMG,node.blue))
        else:
            node.red = None
            node.green = None
            node.blue = None


class TabSplit(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabsplit.ui')
        self.w.canvRed.setMapping(node.mappingR)
        self.w.canvGreen.setMapping(node.mapping)
        self.w.canvBlue.setMapping(node.mappingB)
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # we don't actually care about the mapping here because it's always greyscale
        self.w.canvRed.display(self.node.red)
        self.w.canvGreen.display(self.node.green)
        self.w.canvBlue.display(self.node.blue)
