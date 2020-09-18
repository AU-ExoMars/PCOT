# This is used to test some widgets.

from PyQt5 import QtCore
import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.number
from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image


@xformtype
class XFormTest(XFormType):
    def __init__(self):
        super().__init__("test","utility","0.0.0")
        self.addInputConnector("","img")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        
    def createTab(self,n):
        return TabTest(n)
        
    def generateOutputTypes(self,node):
        # here, the output type matches input 0
        node.matchOutputsToInputs([(0,0)])

    def init(self,node):
        pass
        
    def perform(self,node):
        pass
        

class TabTest(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabtest.ui')
        self.w.value1.init("A",0,1,0.5)
        self.w.value1.changed.connect(self.v1changed)
        self.w.value2.init("B",-10,10,0)
        self.w.value2.changed.connect(self.v2changed)

    def v1changed(self,v):
        print("v1",v)
    def v2changed(self,v):
        print("v2",v)
    def onNodeChanged(self):
        pass
        
    
