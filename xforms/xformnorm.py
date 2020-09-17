import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

# Normalize the image to the 0-1 range,
# across all channels (i.e. the max is taken from all three)

    

@xformtype
class XformNormImage(XFormType):
    """Normalize the image to a single range taken from all three channels"""
    def __init__(self):
        super().__init__("normimage","0.0.0")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        
    def createTab(self,n):
        return TabImage(n)

    def generateOutputTypes(self,node):
        # output type 0 should be the same as input type 0, so a greyscale makes a
        # greyscale and an RGB makes an RGB..
        node.matchOutputsToInputs([(0,0)])
        
    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        node.img = None
        if img is not None:
            maximum = img.img.max()
            if maximum!=0.0:
                node.img = Image(img.img/maximum)
        node.setOutput(0,node.img)
