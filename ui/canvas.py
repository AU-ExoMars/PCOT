from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QTreeView,QFileSystemModel
from PyQt5.QtGui import QImage,QPainter
from PyQt5.QtCore import Qt,QDir
import cv2 as cv


# Canvas widget for showing a CV image

# convert a cv/numpy image to a Qt image
# input must be 3 channel 8 bit
def img2qimage(img):
    height, width, channel = img.shape
    bytesPerLine = 3 * width
    return QImage(img.data, width, height, 
        bytesPerLine, QImage.Format_RGB888)

class Canvas(QtWidgets.QWidget):
    def __init__(self,parent):
        super(QtWidgets.QWidget,self).__init__(parent)
        self.img=None
        self.paintHook=None # an object with a paintEvent() which can do extra drawing
        self.mouseHook=None # an object with a set of mouse events for handling clicks and moves
    # handles 8-bit and 24-bit; also boolean arrays
    def display(self,img):
        if img is not None:
            if img.dtype=='bool':
                img = img.astype(np.ubyte)*255
            if len(img.shape)==2:
                img = cv.merge([img,img,img])
        self.img=img
        self.update()
    def paintEvent(self,event):
        p = QPainter(self)
        p.fillRect(event.rect(),Qt.blue)
        w = self.size().width()
        h = self.size().height()
        if self.img is not None:
            # we paint at the correct aspect ratio, leaving other
            # parts of the rectangle blank
            imgh,imgw,idepth = self.img.shape
            aspect = imgw/imgh
            if h*aspect>w:
                size=(w,int(w/aspect))
                self.scale = imgw/w
            else:
                size=(int(h*aspect),h)
                self.scale = imgh/h

            img = cv.resize(self.img,dsize=size,interpolation=cv.INTER_CUBIC)
            p.drawImage(0,0,img2qimage(img))
            if self.paintHook is not None:
                self.paintHook.canvasPaintHook(p)
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
