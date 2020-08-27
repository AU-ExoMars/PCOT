import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xforms.xform import singleton,XFormType

class TabSplit(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabsplit.ui')
        self.canvRed = self.getUI(ui.canvas.Canvas,'canvRed')
        self.canvGreen = self.getUI(ui.canvas.Canvas,'canvGreen')
        self.canvBlue = self.getUI(ui.canvas.Canvas,'canvBlue')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.canvRed.display(self.node.red)
        self.canvGreen.display(self.node.green)
        self.canvBlue.display(self.node.blue)
        

@singleton
class XformSplit(XFormType):
    def __init__(self):
        super().__init__("split")
        ## our connectors
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("r","imggrey")
        self.addOutputConnector("g","imggrey")
        self.addOutputConnector("b","imggrey")
        
    def createTab(self,mainui,n):
        return TabSplit(mainui,n)

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
            
