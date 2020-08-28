import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType
from xforms.tabimage import TabImage

@singleton
class XformHist(XFormType):
    def __init__(self):
        super().__init__("histequal")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        
    def createTab(self,mainui,n):
        return TabImage(mainui,n)

    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])
        
    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            # deal with 3-channel and 1-channel images
            if len(img.shape)==3:
                r,g,b = cv.split(img)
                r = cv.equalizeHist(r)
                g = cv.equalizeHist(g)
                b = cv.equalizeHist(b)
                node.img = cv.merge((r,g,b))
            else:
                node.img = cv.equalizeHist(img)
                
        node.setOutput(0,node.img)
