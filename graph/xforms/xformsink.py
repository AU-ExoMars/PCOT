import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType
from xforms.tabimage import TabImage

@singleton
class XformSink(XFormType):
    def __init__(self):
        super().__init__("sink")
        ## our connectors
        self.addInputConnector("","img")
    def createTab(self,mainui,n):
        return TabImage(mainui,n)

    def perform(self,node):
        node.img = node.getInput(0)
    def init(self,node):
        node.img = None
