import cv2 as cv
import numpy as np

import conntypes
import ui, ui.tabs, ui.canvas
from xform import xformtype, XFormType, XFormException, Datum
from xforms.tabimage import TabImage
from pancamimage import ImageCube


# Normalize the image to the 0-1 range. The range is taken across all three channels.

def norm(img, mode, mask):
    masked = np.ma.masked_array(img, mask=~mask)
    cp = img.copy()
    mn = masked.min()
    mx = masked.max()
    ex = None

    if mode == 0:  # normalize
        if mn == mx:
            ex = XFormException("DATA", "cannot normalize, image is a single value")
            res = np.zeros(img.shape, np.float32)
        else:
            res = (masked - mn) / (mx - mn)
    elif mode == 1:  # clip
        masked[masked > 1] = 1
        masked[masked < 0] = 0
        res = masked

    np.putmask(cp, mask, res)
    return ex, cp


@xformtype
class XformNormImage(XFormType):
    """Normalize the image to a single range taken from all channels. Honours ROIs"""

    def __init__(self):
        super().__init__("normimage", "processing", "0.0.0")
        self.addInputConnector("", "img")
        self.addOutputConnector("", "img")
        self.hasEnable = True
        self.autoserialise = ('mode',)

    def createTab(self, n, w):
        return TabNorm(n, w)

    def init(self, node):
        node.mode = 0
        node.img = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        node.img = None
        if img is not None:
            if node.enabled:
                subimage = img.subimage()
                ex, newsubimg = norm(subimage.img, node.mode, subimage.fullmask())
                if ex is not None:
                    node.setError(ex)
                node.img = img.modifyWithSub(subimage, newsubimg)
            else:
                node.img = img
            node.img.setMapping(node.mapping)
        node.setOutput(0, Datum(conntypes.IMG, node.img))


class TabNorm(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabnorm.ui')
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.mode.currentIndexChanged.connect(self.modeChanged)
        self.onNodeChanged()

    def modeChanged(self, i):
        self.node.mode = i
        self.changed()

    def onNodeChanged(self):
        self.w.mode.setCurrentIndex(self.node.mode)
        self.w.canvas.display(self.node.img)
