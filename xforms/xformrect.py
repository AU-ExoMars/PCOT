from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


import cv2 as cv
import numpy as np
import math

import ui,ui.tabs,ui.canvas
import utils.text,utils.colour
from xform import xformtype,XFormType
from pancamimage import Image,ROIRect

@xformtype
class XformRect(XFormType):
    """Add a rectangular ROI to an image. At the next operation all ROIs will be grouped together
    used to perform the operation and discarded."""
    def __init__(self):
        super().__init__("rect","regions","0.0.0")
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
        node.colour=(1,1,0)
        
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
            # output image same as input image with same
            # ROIs. I could just pass input to output, but this would
            # mess things up if we go back up the tree again - it would
            # potentially modify the image we passed in.
            o = img.copy()
            roi = ROIRect(x,y,w,h) # create the ROI
            o.rois.append(roi) # and add to the image
            if node.isOutputConnected(0):
                node.setOutput(0,o) # output image and ROI
            if node.isOutputConnected(1):
                # output cropped image: this uses the ROI rectangle to
                # crop the image; we get a numpy image out which we wrap.
                # with no ROIs
                node.setOutput(1,Image(roi.crop(o))) 
            
            # now make the annotated image, which we always do because it's what
            # we display.
            annot = img.img.copy() # numpy copy of image
            # write on it - but we MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
            # with the image! Doing this predictably with the thickness function
            # in cv.rectangle is a pain, so I'm doing it by hand.
            for i in range(node.fontline):
                cv.rectangle(annot,(x-i-1,y-i-1),(x+w+i,y+h+i),node.colour,thickness=1)

            ty = y if node.captiontop else y+h
            utils.text.write(annot,node.caption,x,ty,node.captiontop,node.fontsize,
                node.fontline,node.colour)
            # that's also the image displayed in the tab
            node.img = Image(annot)
            node.img.rois=o.rois # same ROI list as unannotated image
            # output the annotated image
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
        self.w.captionTop.toggled.connect(self.topChanged)
        # sync tab with node
        self.onNodeChanged()
        self.mouseDown=False

    def topChanged(self,checked):
        self.node.captiontop=checked
        self.node.perform()
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
        col = utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.node.colour = col
            self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        if self.node.img is not None:
            self.w.canvas.display(self.node.img)
        self.w.caption.setText(self.node.caption)
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.fontline.setValue(self.node.fontline)
        self.w.captionTop.setChecked(self.node.captiontop)
        r,g,b = [x*255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r,g,b));

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


