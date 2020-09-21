import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

# Normalize the image to the 0-1 range. The range is taken across all three channels.

def norm(img,mask,node):
    masked = np.ma.masked_array(img,mask=~mask)
    cp = img.copy()
    mn = masked.min()
    mx = masked.max()
    
    if mn == mx:
        ui.mainui.error("cannot normalize, image is a single value")
        res = np.full(img.shape,(0,0,255))
    else:
        res = (masked-mn)/(mx-mn)

    np.putmask(cp,mask,res)
    return cp
    

@xformtype
class XformNormImage(XFormType):
    """Normalize the image to a single range taken from all channels. Honours ROIs"""
    def __init__(self):
        super().__init__("normimage","processing","0.0.0")
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
            subimage = img.subimage()
            
            newsubimg = norm(subimage.img,subimage.fullmask(),node)
            node.img = img.modifyWithSub(subimage,newsubimg)
        node.setOutput(0,node.img)
