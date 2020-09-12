from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
import utils,utils.text
from xform import xformtype,XFormType
from pancamimage import Image,ROIRect

@xformtype
class XformRect(XFormType):
    def __init__(self):
        super().__init__("rect","0.0.0")
        self.addInputConnector("","img")
        self.addOutputConnector("img","img") # image+roi
        self.addOutputConnector("crop","img") # cropped image
        self.addOutputConnector("ann","img") # annotated image
        self.addOutputConnector("rect","rect") # rectangle (just the ROI)
        self.autoserialise=('croprect',)
        
    def createTab(self,n):
        return TabRect(n)
        
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0),(1,0),(2,0)])

    def init(self,node):
        node.img = None
        node.croprect=None # would be (x,y,w,h) tuple
        
    def perform(self,node):
        img = node.getInput(0)
        # we do a number of different things depending on which outputs are connected.
        if node.croprect is None or img is None:
            # no rectangle yet or no image
            node.setOutput(0,img)
            node.setOutput(1,img)
            node.setOutput(2,img)
            node.img = img
            node.setOutput(3,None)
        else:
            # need to generate image + ROI
            x,y,w,h = node.croprect
            o = Image(img.img) # make image
            o.roi = ROIRect(x,y,w,h) # slap an ROI on it
            if node.isOutputConnected(0):
                node.setOutput(0,o) # output image and ROI
            if node.isOutputConnected(1):
                # output cropped image: this uses the ROI rectangle to
                # crop the image; we get a numpy image out which we wrap.
                node.setOutput(1,Image(o.roi.crop(o))) 
            # now make the annotated image
            annot = img.img.copy() # numpy copy of image
            # write on it
            cv.rectangle(annot,(x,y),(x+w,y+h),(255,255,0))
            y=y+h # # text below (for now)
            utils.text.write(annot,"FOO",x,y,False,10,3,(255,255,0))
            # that's also the image displayed in the tab
            node.img = Image(annot)
            # output the annotated image too
            node.setOutput(2,node.img)
            # and the raw cropped rectangle
            node.setOutput(3,node.croprect)

class TabRect(ui.tabs.Tab):
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
        if self.node.img is not None:
            self.w.canvas.display(self.node.img)

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


