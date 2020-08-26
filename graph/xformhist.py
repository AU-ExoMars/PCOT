import cv2 as cv
import numpy as np

import tabs,canvas
import xformgraph.xform
from xformgraph.xform import singleton,XFormType

class TabHist(tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'tabimage.ui') # same UI as sink
        self.canvas = self.getUI(canvas.Canvas,'canvas')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.canvas.display(self.node.img)

@singleton
class XformHist(XFormType):
    def __init__(self):
        super().__init__("histequal")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("rgb","img888")
        
    def createTab(self,mainui,n):
        return TabHist(mainui,n)
        
    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            r,g,b = cv.split(img)
            r = cv.equalizeHist(r)
            g = cv.equalizeHist(g)
            b = cv.equalizeHist(b)
            node.img = cv.merge((r,g,b))
        node.setOutput(0,node.img)
