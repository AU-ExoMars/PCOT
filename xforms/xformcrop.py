from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType

@xformtype
class XformCrop(XFormType):
    def __init__(self):
        super().__init__("crop","0.0.1")
        self.addInputConnector("","img")
        self.addOutputConnector("cropped","img")
        self.addOutputConnector("rect","rect")
        self.autoserialise=('croprect',)
        
    def createTab(self,n):
        return TabCrop(n)
        
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])

    def init(self,node):
        node.img = None
        node.croprect=None # would be (x,y,w,h) tuple
        
    def perform(self,node):
        img = node.getInput(0)
        # our image is always the input (but we draw on it), the output is the crop.
        node.img = img
        if node.croprect is not None and img is not None:
            x,y,w,h = node.croprect
            print("CROPPING")
            out = img[y:y+h,x:x+w]
            ui.mainui.log("Cropped: x={} y={} w={} h={}".format(x,y,w,h))
        else:
            out = img
        node.setOutput(0,out)
        node.setOutput(1,node.croprect)

class TabCrop(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabimage.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook=self
        self.w.canvas.mouseHook=self
        # sync tab with node
        self.onNodeChanged()
        self.mouseDown=False

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # we make a copy of the image and draw the rectangle on that, it's more accurate
        # (at the cost of memory)
        if self.node.img is not None:
            img = self.node.img.copy()
            if self.node.croprect is not None:
                x,y,w,h = self.node.croprect
                cv.rectangle(img,(x,y),(x+w,y+h),(255,255,0))
            self.w.canvas.display(img)

    # extra drawing!
    def canvasPaintHook(self,p):
        # we could draw the rectangle in here (dividing all sizes down by the canvas scale)
        # but it's more accurate done as above in onNodeChanged
        pass
            
    def canvasMouseMoveEvent(self,x2,y2,e):
        if self.mouseDown:
            p=e.pos()
            x,y,w,h = self.node.croprect
            w = x2-x
            h = y2-y
            if w<10:
                w=10
            if h<10:
                h=10
            self.node.croprect=(x,y,w,h)
            self.node.perform()
        self.w.canvas.update()
        
    def canvasMousePressEvent(self,x,y,e):
        p = e.pos()
        w = 10 # min crop size
        h = 10
        self.mouseDown=True
        self.node.croprect=(x,y,w,h)
        self.node.perform()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self,x,y,e):
        self.mouseDown=False


