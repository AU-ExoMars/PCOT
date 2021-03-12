import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas
from xform import xformtype, XFormType, XFormException
from xforms.tabimage import TabImage
from pancamimage import ImageCube


# Normalize the image to the 0-1 range. The range is taken across all three channels.

def norm(img, mask):
    masked = np.ma.masked_array(img, mask=~mask)
    cp = img.copy()
    mn = masked.min()
    mx = masked.max()

    if mn == mx:
        ex = XFormException("DATA", "cannot normalize, image is a single value")
        res = np.zeros(img.shape, np.float32)
    else:
        ex = None
        res = (masked - mn) / (mx - mn)

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

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0)
        node.img = None
        if img is not None:
            if node.enabled:
                subimage = img.subimage()
                ex, newsubimg = norm(subimage.img, subimage.fullmask())
                if ex is not None:
                    node.setError(ex)
                node.img = img.modifyWithSub(subimage, newsubimg)
            else:
                node.img = img
            node.img.setMapping(node.mapping)
        node.setOutput(0, node.img)
