import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from pancamimage import Image,ROIRect

@xformtype
class XformSplit(XFormType):
    """Splits an RGB image into three greyscale images"""
    def __init__(self):
        super().__init__("split","colour","0.0.0")
        ## our connectors
        self.addInputConnector("rgb","imgrgb")
        self.addOutputConnector("r","imggrey")
        self.addOutputConnector("g","imggrey")
        self.addOutputConnector("b","imggrey")
        
    def createTab(self,n,w):
        return TabSplit(n,w)

    def init(self,node):
        node.red = None
        node.green = None
        node.blue = None

    def perform(self,node):
        img = node.getInput(0)
        if img is not None:
            # image MUST have three sources - the input type should insure this,
            # because we only accept RGB
            r,g,b = cv.split(img.rgb()) # kind of pointless on a greyscale..
            node.red = Image(r,[img.sources[0]])
            node.green = Image(g,[img.sources[1]])
            node.blue = Image(b,[img.sources[2]])
            node.setOutput(0,node.red)
            node.setOutput(1,node.green)
            node.setOutput(2,node.blue)
        else:
            node.red=None
            node.green=None
            node.blue=None
            
class TabSplit(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabsplit.ui')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvRed.display(self.node.red)
        self.w.canvGreen.display(self.node.green)
        self.w.canvBlue.display(self.node.blue)
        

