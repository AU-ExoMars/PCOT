from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.mplwidget
from xform import xformtype,XFormType
from pancamimage import Image

@xformtype
class XformGradient(XFormType):
    """Convert a greyscale image to a colour gradient image for better visibility"""
    
    def __init__(self):
        super().__init__("gradient","data","0.0.0")
        self.addInputConnector("","imggrey")
        self.addOutputConnector("","imgrgb")
        
    def createTab(self,n):
        return TabGradient(n)
        
    def init(self,node):
        pass
        
    def perform(self,node):
        pass
        

class TabGradient(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabgrad.ui')
        self.w.gradient.gradientChanged.connect(self.gradientChanged)
        self.onNodeChanged()
            
    def onNodeChanged(self):
        pass

    def gradientChanged(self):
        print(self.w.gradient.gradient())
