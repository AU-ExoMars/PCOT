import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

@xformtype
class XformSink(XFormType):
    def __init__(self):
        super().__init__("sink")
        ## our connectors
        self.ver="0.0.0"
        self.addInputConnector("","img")
    def createTab(self,n):
        return TabImage(n)

    def perform(self,node):
        node.img = node.getInput(0)
    def init(self,node):
        node.img = None
