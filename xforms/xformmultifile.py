from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt,QDir

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from pancamimage import Image

@xformtype
class XFormMultiFile(XFormType):
    """Load multiple image files into greyscale channels"""
    def __init__(self):
        super().__init__("multifile","0.0.0")
        
    def createTab(self,n):
        pass
        
    def init(self,node):
        pass
        
    def perform(self,node):
        pass
        
