import cv2 as cv
import numpy as np

import tabs,canvas
import xformgraph.xform
from xformgraph.xform import singleton,XFormType

class TabSink(tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'tabimage.ui')
        self.canvas = self.getUI(canvas.Canvas,'canvas')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.canvas.display(self.node.getInput(0))
        

@singleton
class XformSink(XFormType):
    def __init__(self):
        super().__init__("sink")
        ## our connectors
        self.addInputConnector("rgb","img888")
    def createTab(self,mainui,n):
        return TabSink(mainui,n)

