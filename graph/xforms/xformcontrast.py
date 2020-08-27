from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType

def contrast(img,tol):
    B = img.astype(np.float)
    for b in range(3):
            # find lower and upper limit for contrast stretching
        low, high = np.percentile(B[:,:,b], 100*tol), np.percentile(B[:,:,b], 100-100*tol)
        B[B<low] = low
        B[B>high] = high
        # ...rescale the color values to 0..255
        B[:,:,b] = 255 * (B[:,:,b] - B[:,:,b].min())/(B[:,:,b].max() - B[:,:,b].min())
    return B.astype(np.uint8)

class TabContrast(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabcontrast.ui') # same UI as sink
        self.canvas = self.getUI(ui.canvas.Canvas,'canvas')
        self.dial = self.getUI(QtWidgets.QDial,'dial')
        self.dial.valueChanged.connect(self.setContrast)

        # sync tab with node
        self.onNodeChanged()

    def setContrast(self,v):
        # when a control changes, update node and perform
        self.node.tol = v/200
        self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.dial.setValue(self.node.tol*200)        
        self.canvas.display(self.node.img)

@singleton
class XformContrast(XFormType):
    def __init__(self):
        super().__init__("contrast stretch")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("rgb","img888")
        
    def createTab(self,mainui,n):
        return TabContrast(mainui,n)
        
    def init(self,node):
        node.img = None
        node.tol = 0.2

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            node.img = contrast(img,node.tol)
        node.setOutput(0,node.img)
