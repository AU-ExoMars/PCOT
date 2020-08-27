import cv2 as cv
import numpy as np

import tabs,canvas
import xformgraph.xform
from xformgraph.xform import singleton,XFormType
from xformimage import TabImage

@singleton
class XformHist(XFormType):
    def __init__(self):
        super().__init__("histequal")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("rgb","img888")
        
    def createTab(self,mainui,n):
        return TabImage(mainui,n)
        
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
