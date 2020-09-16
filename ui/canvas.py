import math
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QTreeView,QFileSystemModel
from PyQt5.QtGui import QImage,QPainter
from PyQt5.QtCore import Qt,QDir
import cv2 as cv
import numpy as np


# Canvas widget for showing a CV image

# convert a cv/numpy image to a Qt image
# input must be 3 channels, 0-1 floats
def img2qimage(img):
    i = img*255.0
    i = i.astype(np.ubyte)
    height, width, channel = i.shape
    bytesPerLine = 3 * width
    return QImage(i.data, width, height, 
        bytesPerLine, QImage.Format_RGB888)

# the actual drawing widget
class InnerCanvas(QtWidgets.QWidget):
    def __init__(self,canv,parent=None):
        super(QtWidgets.QWidget,self).__init__(parent)
        self.img=None
        self.canv=canv
        self.reset()
    def reset(self):
        # not the same as self.scale, which defines the scale of the image 
        # to fit in the on-screen window at 1x resolution.
        self.zoomscale=1 
        # pixel at top-left of visible image within window (when zoomed)
        self.x=0
        self.y=0
        
    # handles 1 and 3 channels
    def display(self,img):
        if img is not None:
            self.img = img.rgb() # convert to RGB
        else:
            self.img = None
        self.reset()
        self.update()
    def paintEvent(self,event):
        p = QPainter(self)
        p.fillRect(event.rect(),Qt.blue)
        w = self.size().width()
        h = self.size().height()
        # here self.img is a numpy image
        if self.img is not None:
            imgh,imgw = self.img.shape[0],self.img.shape[1]
            # cut out the part of the image that we want - from (x,y), with size
            # width*zoomscale,height*zoomscale
            cutw = int(imgw*self.zoomscale)
            cuth = int(imgh*self.zoomscale)
            cutx = int(self.x)
            cuty = int(self.y)
            print(cutx,cuty,cutw,cuth)
            img = self.img[cuty:cuty+cuth,cutx:cutx+cutw]
            print(img.shape)
            # we paint at the correct aspect ratio, leaving other
            # parts of the rectangle blank
            aspect = cutw/cuth
            if h*aspect>w:
                size=(w,int(w/aspect))
                self.scale = cutw/w
            else:
                size=(int(h*aspect),h)
                self.scale = cuth/h
            # cubic produced odd artifacts on float images
            img = cv.resize(img,dsize=size,interpolation=cv.INTER_AREA)
            p.drawImage(0,0,img2qimage(img))
            if self.canv.paintHook is not None:
                self.canv.paintHook.canvasPaintHook(p)
        else:
            self.scale=1
        p.end()
        
    def mousePressEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMousePressEvent(x,y,e)
        return super().mousePressEvent(e)

    def mouseMoveEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMouseMoveEvent(x,y,e)
        return super().mouseMoveEvent(e)

    def mouseReleaseEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMouseReleaseEvent(x,y,e)
        return super().mouseReleaseEvent(e)

    def wheelEvent(self,e):
        # get the mousepos in the image and calculate the new zoom
        wheel = 1 if e.angleDelta().y()<0 else -1
        x = e.pos().x()
        y = e.pos().y()
        newzoom = self.zoomscale*math.exp(wheel*0.2)
        
        # get image coords, and clip the event's coords to those
        # (to make sure we're not clicking on the background of the canvas)
        imgh,imgw = self.img.shape[0],self.img.shape[1]
        if x>=imgw:
            x=imgw-1
        if y>=imgh:
            y=imgh-1
            
        # work out the new image size
        cutw = int(imgw*newzoom)
        cuth = int(imgh*newzoom)
        # too small? too big? abort!
        if cutw==0 or cuth==0 or newzoom>1:
            return

        # calculate change in zoom and use it to move the offset
        zoomchange = newzoom-self.zoomscale
        self.x -= zoomchange*x
        self.y -= zoomchange*y
        # set the new zoom
        self.zoomscale=newzoom
        # clip the change
        if self.x<0:
            self.x=0
        if self.y<0:
            self.y=0
        # update scrollbars and image
        self.canv.setScrollBarsFromCanvas()
        self.update()

        
class Canvas(QtWidgets.QWidget):
    def __init__(self,parent):
        super(QtWidgets.QWidget,self).__init__(parent)
        self.paintHook=None # an object with a paintEvent() which can do extra drawing
        self.mouseHook=None # an object with a set of mouse events for handling clicks and moves

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        self.canvas = InnerCanvas(self)
        layout.addWidget(self.canvas,0,0)
        
        self.scrollV=QtWidgets.QScrollBar(Qt.Vertical)
        self.scrollV.valueChanged.connect(self.vertScrollChanged)
        layout.addWidget(self.scrollV,0,1)
        
        self.scrollH=QtWidgets.QScrollBar(Qt.Horizontal)
        self.scrollH.valueChanged.connect(self.horzScrollChanged)
        layout.addWidget(self.scrollH,1,0)
        
    def display(self,img):
        self.canvas.display(img)
        self.setScrollBarsFromCanvas()
        
    def setScrollBarsFromCanvas(self):
        # set the scroll bars from the position and zoom of the underlying canvas
        # first, we set the min and max of the bars to the pixel range, minus the size of the bar itself
        self.scrollH.setMinimum(0)
        self.scrollV.setMinimum(0)
        img = self.canvas.img
        if img is not None:
            h,w = img.shape[:2]
            # work out the size of the scroll bar from the zoom factor
            hsize = w*self.canvas.zoomscale
            vsize = h*self.canvas.zoomscale
            self.scrollH.setPageStep(hsize)
            self.scrollV.setPageStep(vsize)
            # and set the actual scroll bar size
            self.scrollH.setMaximum(w-hsize)
            self.scrollV.setMaximum(h-vsize)
            # and the position
            self.scrollH.setValue(self.canvas.x)
            self.scrollV.setValue(self.canvas.y)
        
    def vertScrollChanged(self,v):
        pass
    def horzScrollChanged(self,v):
        pass

