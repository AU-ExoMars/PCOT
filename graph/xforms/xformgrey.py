import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType
from xforms.tabimage import TabImage

@singleton
class XformGrey(XFormType):
    def __init__(self):
        super().__init__("greyscale")
        self.addInputConnector("","img888")
        self.addOutputConnector("","imggrey")
        
    def createTab(self,mainui,n):
        return TabImage(mainui,n)

    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            node.img = cv.cvtColor(img,cv.COLOR_RGB2GRAY)
                
        node.setOutput(0,node.img)
