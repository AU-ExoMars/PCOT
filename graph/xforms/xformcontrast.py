from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType

def contrast1(img,tol):
    B = img.astype(np.float)
    # find lower and upper limit for contrast stretching
    low, high = np.percentile(B, 100*tol), np.percentile(B, 100-100*tol)
    B[B<low] = low
    B[B>high] = high
    # ...rescale the color values to 0..255
    B = 255 * (B - B.min())/(B.max() - B.min())
    return B.astype(np.uint8)

def contrast(img,tol):
    return cv.merge([contrast1(x,tol) for x in cv.split(img)])
    

class TabContrast(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabcontrast.ui') # same UI as sink
        self.w.dial.valueChanged.connect(self.setContrast)

        # sync tab with node
        self.onNodeChanged()

    def setContrast(self,v):
        # when a control changes, update node and perform
        self.node.tol = v/200
        self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.dial.setValue(self.node.tol*200)        
        self.w.canvas.display(self.node.img)

@singleton
class XformContrast(XFormType):
    def __init__(self):
        super().__init__("contrast stretch")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        
    def createTab(self,mainui,n):
        return TabContrast(mainui,n)
        
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])

    def init(self,node):
        node.img = None
        node.tol = 0.2

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            if len(img.shape)==3:
                node.img = contrast(img,node.tol)
            else:
                node.img = contrast1(img,node.tol)
        node.setOutput(0,node.img)
