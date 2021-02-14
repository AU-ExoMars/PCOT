import cv2 as cv
import numpy as np

import ui.tabs, ui.canvas
from channelsource import BLUEINTERNALSOURCE, GREENINTERNALSOURCE, REDINTERNALSOURCE
from xform import xformtype, XFormType
from xforms.tabimage import TabImage
from pancamimage import ImageCube
import functools


@xformtype
class XformMerge(XFormType):
    """Merge up to 3 channels into a single image. This is typically RGB but a 2-channel image can
    be created by only connecting 2 channels and turning off the 'pad to 3 channels' option.
    Merging only works on entire images - ROIs are ignored."""

    def __init__(self):
        super().__init__("merge", "colour", "0.0.0")
        ## our connectors
        self.addInputConnector("r", "imggrey")
        self.addInputConnector("g", "imggrey")
        self.addInputConnector("b", "imggrey")
        self.addOutputConnector("", "img")  # output might not be RGB
        self.autoserialise = ('addblack',)

    def createTab(self, n, w):
        return TabMerge(n, w)

    def generateOutputTypes(self, n):
        # count connected inputs
        ct = sum([0 if x is None else 1 for x in n.inputs])
        if ct == 1:
            tp = 'imggrey'
        elif ct == 3 or n.addblack:
            tp = 'imgrgb'
        else:
            tp = 'imgstrange'
        n.changeOutputType(0, tp)

    def init(self, node):
        node.img = None
        node.addblack = True

    def perform(self, node):
        r = node.getInput(0)
        g = node.getInput(1)
        b = node.getInput(2)
        node.img = None  # preset the internal value

        # get shapes; this still works because Image has shape
        rs = None if r is None else r.shape
        gs = None if g is None else g.shape
        bs = None if b is None else b.shape

        # get the shape of one of them
        s = None
        if rs is not None:
            s = rs
        elif gs is not None:
            s = gs
        elif bs is not None:
            s = bs

        # make sure is at least one of them present
        if s is None:
            node.setOutput(0, None)
            return

        # all that are present are the same size
        if (rs is not None and rs != s) or (gs is not None and gs != s) or (bs is not None and bs != s):
            node.setOutput(0, None)
            return
        if node.addblack:
            # make a black
            black = np.zeros(s, np.float32)
            if b is None:
                b = ImageCube(black, [{BLUEINTERNALSOURCE}])
            if g is None:
                g = ImageCube(black, [{GREENINTERNALSOURCE}])
            if r is None:
                r = ImageCube(black, [{REDINTERNALSOURCE}])
            lst = [r, g, b]
        else:
            lst = [x for x in [r, g, b] if x is not None]

        if len(lst) == 1:
            node.img = ImageCube(lst[0].img, lst[0].sources)  # just merging one channel??
        else:
            # here we assume there can only be one channel in each source image,
            # and we just bundle sources together. We use None for images with no source.
            sources = [x.sources[0] for x in lst]
            node.img = ImageCube(cv.merge([x.img for x in lst]), sources)
        node.setOutput(0, node.img)


class TabMerge(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabmerge.ui')
        self.w.addblack.toggled.connect(self.addBlackChanged)
        self.w.canvas.setMapping(node.mapping)
        # sync tab with node
        self.onNodeChanged()

    def addBlackChanged(self, b):
        self.node.addblack = b
        self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.addblack.setChecked(self.node.addblack)
        self.w.canvas.display(self.node.img)
