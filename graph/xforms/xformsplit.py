import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType

@xformtype
class XformSplit(XFormType):
    def __init__(self):
        super().__init__("split","0.0.0")
        ## our connectors
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("r","imggrey")
        self.addOutputConnector("g","imggrey")
        self.addOutputConnector("b","imggrey")
        
    def createTab(self,n):
        return TabSplit(n)

    def init(self,node):
        node.red = None
        node.green = None
        node.blue = None

    def perform(self,node):
        img = node.getInput(0)
        if img is not None:
            node.red,node.green,node.blue = cv.split(img)
            node.setOutput(0,node.red)
            node.setOutput(1,node.green)
            node.setOutput(2,node.blue)
        else:
            node.red=None
            node.green=None
            node.blue=None
            
class TabSplit(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabsplit.ui')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvRed.display(self.node.red)
        self.w.canvGreen.display(self.node.green)
        self.w.canvBlue.display(self.node.blue)
        

