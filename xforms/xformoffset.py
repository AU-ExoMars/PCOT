from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.mplwidget
from xform import xformtype,XFormType
from pancamimage import Image

@xformtype
class XFormOffset(XFormType):
    """offset an image. Will create a zero band on one edge and clip on the opposite.
    ROIs are not honoured, but are passed through."""
    def __init__(self):
        super().__init__("offset","processing","0.0.0")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        self.autoserialise=('x','y')
        self.hasEnable = True

    def createTab(self,n,w):
        return TabOffset(n,w)

    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])

    def init(self,node):
        node.img = None
        node.x = 0
        node.y = 0
        
    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        elif not node.enabled:
            node.img = img
        else:
            # make new image the size of the old one
            newimg = np.zeros(img.img.shape,dtype=np.float32)
            xs = -min(node.x,0) # offset into source image
            ys = -min(node.y,0) # offset into source image
            xd = max(node.x,0) # offset into dest
            yd = max(node.y,0) # offset into dest
            # size of region to copy
            w = img.w-max(abs(xd),abs(xs))
            h = img.h-max(abs(yd),abs(ys))
            
            s = img.img[ys:ys+h,xs:xs+w]
            newimg[yd:yd+h,xd:xd+w]=s
            # remember to copy ROI            
            node.img = Image(newimg,img.sources)
            

        node.setOutput(0,node.img)

class TabOffset(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/taboffset.ui')
        self.w.xoff.editingFinished.connect(self.xChanged)
        self.w.yoff.editingFinished.connect(self.yChanged)
        self.onNodeChanged()
        
    def xChanged(self):
        self.node.x = int(self.w.xoff.text())
        self.node.perform()
    def yChanged(self):
        self.node.y = int(self.w.yoff.text())
        self.node.perform()

    def onNodeChanged(self):
        self.w.xoff.setText(str(self.node.x))
        self.w.yoff.setText(str(self.node.y))
        self.w.canvas.display(self.node.img)
