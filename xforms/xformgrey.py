import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas

from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

@xformtype
class XformGrey(XFormType):
    """Converts an RGB image to greyscale."""
    def __init__(self):
        super().__init__("greyscale","0.0.0")
        self.addInputConnector("","imgrgb")
        self.addOutputConnector("","imggrey")
        
    def createTab(self,n):
        return TabImage(n)

    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            print(img.img.shape,img.img.dtype)
            if img.channels != 3:
                raise Exception("Image must be RGB for greyscale conversion")
            node.img = Image(cv.cvtColor(img.img,cv.COLOR_RGB2GRAY))
                
        node.setOutput(0,node.img)
