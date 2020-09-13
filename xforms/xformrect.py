from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


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
        self.autoserialise=('croprect','caption','captiontop','fontsize','fontline','colour')
        
    def createTab(self,n):
        return TabRect(n)
        
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0),(1,0),(2,0)])

    def init(self,node):
        node.img = None
        node.croprect=None # would be (x,y,w,h) tuple
        node.caption = ''
        node.captiontop = False
        node.fontsize=10
        node.fontline=2
        node.colour=(255,255,0)
        
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
            roi = ROIRect(x,y,w,h) # create the ROI
            o.rois.append(roi) # and add to the image
            if node.isOutputConnected(0):
                node.setOutput(0,o) # output image and ROI
            if node.isOutputConnected(1):
                print("Node is connected")
                # output cropped image: this uses the ROI rectangle to
                # crop the image; we get a numpy image out which we wrap.
                node.setOutput(1,Image(roi.crop(o))) 
            else:
                print("OP 1 not connected")
            
            # now make the annotated image
            annot = img.img.copy() # numpy copy of image
            # write on it
            cv.rectangle(annot,(x,y),(x+w,y+h),node.colour,thickness=node.fontline)

            ty = y if node.captiontop else y+h
            utils.text.write(annot,"FOO",x,y,node.captiontop,node.fontsize,
                node.fontline,node.colour)
            # that's also the image displayed in the tab
            node.img = Image(annot)
            # output the annotated image too
            node.setOutput(2,node.img)
            # and the raw cropped rectangle
            node.setOutput(3,node.croprect)

class TabRect(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabrect.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook=self
        self.w.canvas.mouseHook=self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        # sync tab with node
        self.onNodeChanged()
        self.mouseDown=False

    def fontSizeChanged(self,i):
        self.node.fontsize=i
        self.node.perform()
    def textChanged(self,t):
        self.node.caption=t
        self.node.perform()
    def fontLineChanged(self,i):
        self.node.fontline=i
        self.node.perform()
    def colourPressed(self):
        r,g,b = self.node.colour
        curcol = QColor(r,g,b)
        col=QtWidgets.QColorDialog.getColor(curcol,ui.mainui)
        if col.isValid():
            self.node.colour = (col.red(),col.green(),col.blue())
            self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        if self.node.img is not None:
            self.w.canvas.display(self.node.img)
        self.w.caption.setText(self.node.caption)
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.fontline.setValue(self.node.fontline)

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


