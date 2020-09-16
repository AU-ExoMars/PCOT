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

class Canvas(QtWidgets.QWidget):
    def __init__(self,parent):
        super(QtWidgets.QWidget,self).__init__(parent)
        self.img=None
        self.paintHook=None # an object with a paintEvent() which can do extra drawing
        self.mouseHook=None # an object with a set of mouse events for handling clicks and moves
    # handles 1 and 3 channels
    def display(self,img):
        if img is not None:
            self.img = img.rgb() # convert to RGB
        else:
            self.img = None
        self.update()
    def paintEvent(self,event):
        p = QPainter(self)
        p.fillRect(event.rect(),Qt.blue)
        w = self.size().width()
        h = self.size().height()
        # here self.img is a numpy image
        if self.img is not None:
            # we paint at the correct aspect ratio, leaving other
            # parts of the rectangle blank
            imgh,imgw = self.img.shape[0],self.img.shape[1]
            aspect = imgw/imgh
            if h*aspect>w:
                size=(w,int(w/aspect))
                self.scale = imgw/w
            else:
                size=(int(h*aspect),h)
                self.scale = imgh/h
            # cubic produced odd artifacts on float images
            img = cv.resize(self.img,dsize=size,interpolation=cv.INTER_AREA)
            p.drawImage(0,0,img2qimage(img))
            if self.paintHook is not None:
                self.paintHook.canvasPaintHook(p)
        else:
            self.scale=1
        p.end()
        
    def mousePressEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.mouseHook is not None:
            self.mouseHook.canvasMousePressEvent(x,y,e)
        return super().mousePressEvent(e)

    def mouseMoveEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.mouseHook is not None:
            self.mouseHook.canvasMouseMoveEvent(x,y,e)
        return super().mouseMoveEvent(e)

    def mouseReleaseEvent(self,e):
        x= int(e.pos().x()*self.scale)
        y= int(e.pos().y()*self.scale)
        if self.mouseHook is not None:
            self.mouseHook.canvasMouseReleaseEvent(x,y,e)
        return super().mouseReleaseEvent(e)
