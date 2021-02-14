## @package ui.canvas
# Canvas widget for showing a CV image
#
import math
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np
import ui.tabs
from channelsource import IChannelSource
from pancamimage import ImageCube, ChannelMapping
from xform import XForm


## convert a cv/numpy image to a Qt image
# input must be 3 channels, 0-1 floats


def img2qimage(img):
    i = img * 255.0
    i = i.astype(np.ubyte)
    height, width, channel = i.shape
    bytesPerLine = 3 * width
    return QImage(i.data, width, height,
                  bytesPerLine, QImage.Format_RGB888)


## the actual drawing widget, contained within the Canvas widget
class InnerCanvas(QtWidgets.QWidget):
    ## @var img
    # the numpy image we are rendering (1 or 3 chans)
    ## @var canv
    # our main Canvas widget, which contains this widget
    ## @var zoomscale
    # the current zoom level: 1 to contain the entire image onscreen
    ## @var scale
    # defines the zoom factor which scales the canvas to hold the image
    ## @var x
    # offset of top left pixel in canvas
    ## @var y
    # offset of top left pixel in canvas

    ## constructor
    def __init__(self, canv, parent=None):
        super().__init__(parent)
        self.img = None
        self.desc = ""
        self.zoomscale = 1
        self.x = 0
        self.y = 0
        self.canv = canv
        self.reset()

    ## resets the canvas to zoom level 1, top left pan
    def reset(self):
        # not the same as self.scale, which defines the scale of the image 
        # to fit in the on-screen window at 1x resolution.
        self.zoomscale = 1
        # pixel at top-left of visible image within window (when zoomed)
        self.x = 0
        self.y = 0

    ## returns the main window for this canvas
    def getMainWindow(self):
        # this is ugly, but the only sane way of getting a backref to the containing main window.
        # We scan up until we get the tab, and get the main window from that. This will work
        # even when the tab has expanded.
        w = self.parent()
        while w is not None and not isinstance(w, ui.tabs.Tab):
            w = w.parent()
        if w is None:
            raise Exception("can't get main window from canvas")
        return w.window

    ## display an image (handles 1 and 3 channels) next time paintEvent
    # happens, and update to cause that. Allow it to handle None too.
    def display(self, img: ImageCube, mapping: ChannelMapping):
        if img is not None:
            self.desc = img.getDesc(self.getMainWindow(), mapping)
            img = img.rgb(mapping)  # convert to RGB
            # only reset the image zoom if the shape has changed
            if self.img is None or self.img.shape[:2] != img.shape[:2]:
                self.reset()
            self.img = img
        else:
            self.img = None
            self.reset()
        self.update()

    ## the paint event
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(event.rect(), Qt.blue)
        widgw = self.size().width()  # widget dimensions
        widgh = self.size().height()
        # here self.img is a numpy image
        if self.img is not None:
            imgh, imgw = self.img.shape[0], self.img.shape[1]

            # work out the "base scale" so that a zoomscale of 1 fits the entire
            # image            
            aspect = imgw / imgh
            if widgh * aspect > widgw:
                self.scale = imgw / widgw
            else:
                self.scale = imgh / widgh

            scale = self.zoomscale * self.scale

            # work out the size of the widget in image pixel coordinates
            cutw = int(widgw * scale)
            cuth = int(widgh * scale)
            # get the top-left coordinate and cut the area.            
            cutx = int(self.x)
            cuty = int(self.y)
            img = self.img[cuty:cuty + cuth, cutx:cutx + cutw]
            # now get the size of the image that was actually cut (some areas may be out of range)
            cuth, cutw = img.shape[:2]
            # now resize the cut area up to fit the widget. Using area interpolation here:
            # cubic produced odd artifacts on float images
            img = cv.resize(img, dsize=(int(cutw / scale), int(cuth / scale)), interpolation=cv.INTER_AREA)
            p.drawImage(0, 0, img2qimage(img))
            if self.canv.paintHook is not None:
                self.canv.paintHook.canvasPaintHook(p)
            p.setPen(Qt.yellow)
            p.setBrush(Qt.yellow)
            r = QtCore.QRect(0, widgh - 20, widgw, 20)
            p.drawText(r, Qt.AlignLeft, self.desc)

        else:
            self.scale = 1
        p.end()

    ## given point in the widget, return coords in the image. Takes a QPoint.
    def getImgCoords(self, p: QtCore.QPoint):
        x = int(p.x() * (self.scale * self.zoomscale) + self.x)
        y = int(p.y() * (self.scale * self.zoomscale) + self.y)
        return x, y

    ## mouse press handler, can delegate to a hook
    def mousePressEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMousePressEvent(x, y, e)
        return super().mousePressEvent(e)

    ## mouse move handler, can delegate to a hook
    def mouseMoveEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMouseMoveEvent(x, y, e)
        return super().mouseMoveEvent(e)

    ## mouse release handler, can delegate to a hook
    def mouseReleaseEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        if self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMouseReleaseEvent(x, y, e)
        return super().mouseReleaseEvent(e)

    ## mouse wheel handler, changes zoom
    def wheelEvent(self, e):
        # get the mousepos in the image and calculate the new zoom
        wheel = 1 if e.angleDelta().y() < 0 else -1
        x, y = self.getImgCoords(e.pos())
        newzoom = self.zoomscale * math.exp(wheel * 0.2)

        # can't zoom when there's no image
        if self.img is None:
            return

        # get image coords, and clip the event's coords to those
        # (to make sure we're not clicking on the background of the canvas)
        imgh, imgw = self.img.shape[0], self.img.shape[1]
        if x >= imgw:
            x = imgw - 1
        if y >= imgh:
            y = imgh - 1

        # work out the new image size
        cutw = int(imgw * newzoom)
        cuth = int(imgh * newzoom)
        # too small? too big? abort!
        if cutw == 0 or cuth == 0 or newzoom > 1:
            return

        # calculate change in zoom and use it to move the offset
        zoomchange = newzoom - self.zoomscale
        self.x -= zoomchange * x
        self.y -= zoomchange * y
        # set the new zoom
        self.zoomscale = newzoom
        # clip the change
        if self.x < 0:
            self.x = 0
        if self.y < 0:
            self.y = 0
        # update scrollbars and image
        self.canv.setScrollBarsFromCanvas()
        self.update()


def makeTopBarLabel(t):
    lab = QtWidgets.QLabel(t)
    lab.setMaximumHeight(15)
    return lab


## the containing widget, holding scroll bars and InnerCanvas widget

class Canvas(QtWidgets.QWidget):
    ## @var paintHook
    # an object with a paintEvent() which can do extra drawing (or None)
    ## @var mouseHook
    # an object with a set of mouse events for handling clicks and moves (or None)

    ## constructor
    def __init__(self, parent):
        super(QtWidgets.QWidget, self).__init__(parent)
        self.paintHook = None
        self.mouseHook = None

        # outer layout is a vertical box - the topbar and canvas+scrollbars are in this
        outerlayout = QtWidgets.QVBoxLayout()
        self.setLayout(outerlayout)

        # the topbar is a grid, with labels on top (red,green,blue)
        # and channel name comboboxes below
        topbar = QtWidgets.QGridLayout()
        outerlayout.addLayout(topbar)

        topbar.addWidget(makeTopBarLabel("RED source"), 0, 0)
        topbar.addWidget(makeTopBarLabel("GREEN source"), 0, 1)
        topbar.addWidget(makeTopBarLabel("BLUE source"), 0, 2)

        # these are the actual widgets specifying which channel in the cube is viewed.
        # We need to deal with these carefully.
        self.redChanCombo = QtWidgets.QComboBox()
        self.redChanCombo.currentIndexChanged.connect(self.redIndexChanged)
        topbar.addWidget(self.redChanCombo, 1, 0)
        self.greenChanCombo = QtWidgets.QComboBox()
        self.greenChanCombo.currentIndexChanged.connect(self.greenIndexChanged)
        topbar.addWidget(self.greenChanCombo, 1, 1)
        self.blueChanCombo = QtWidgets.QComboBox()
        self.blueChanCombo.currentIndexChanged.connect(self.blueIndexChanged)
        topbar.addWidget(self.blueChanCombo, 1, 2)

        layout = QtWidgets.QGridLayout()
        outerlayout.addLayout(layout)

        self.canvas = InnerCanvas(self)
        layout.addWidget(self.canvas, 0, 0)

        self.scrollV = QtWidgets.QScrollBar(Qt.Vertical)
        self.scrollV.valueChanged.connect(self.vertScrollChanged)
        layout.addWidget(self.scrollV, 0, 1)

        self.scrollH = QtWidgets.QScrollBar(Qt.Horizontal)
        self.scrollH.valueChanged.connect(self.horzScrollChanged)
        layout.addWidget(self.scrollH, 1, 0)

        self.resetButton = QtWidgets.QPushButton()
        layout.addWidget(self.resetButton, 1, 1)
        self.resetButton.clicked.connect(self.reset)

        # the mapping we are using - the node owns this, we just get a ref. when
        # the tab is created
        self.mapping = None
        # previous image (in case mapping changes)
        self.previmg = None

    def setMapping(self, mapping):
        self.mapping = mapping

    def redIndexChanged(self, i):
        print("RED CHANGED TO", i)
        self.mapping.red = i
        self.redisplay()

    def greenIndexChanged(self, i):
        print("GREEN CHANGED TO", i)
        self.mapping.green = i
        self.redisplay()

    def blueIndexChanged(self, i):
        print("BLUE CHANGED TO", i)
        self.mapping.blue = i
        self.redisplay()

    ## this initialises a combo box, setting the possible values to be the channels in the image
    # input
    def addChannelsToChannelCombo(self, combo: QtWidgets.QComboBox, img: ImageCube):
        combo.blockSignals(True) # temporarily disable signals to avoid indexChanged calls
        combo.clear()
        for i in range(0, img.channels):
            # adds descriptor string and integer channels index
            combo.addItem(IChannelSource.stringForSet(img.sources[i],
                                                      self.canvas.getMainWindow().captionType))  # ugly
        combo.blockSignals(False)

    def setCombosToImageChannels(self, img):
        self.addChannelsToChannelCombo(self.redChanCombo, img)
        self.addChannelsToChannelCombo(self.greenChanCombo, img)
        self.addChannelsToChannelCombo(self.blueChanCombo, img)

    ## set this canvas (actually the InnerCanvas) to hold an image.

    def display(self, img: ImageCube):
        if img is not None:
            # ensure there is a valid mapping
            self.mapping.ensureValid(img)
            # now make the combo box options match the sources in the image
            # and finally make the selection each each box match the actual channel assignment
            self.setCombosToImageChannels(img)
            self.redChanCombo.setCurrentIndex(self.mapping.red)
            self.greenChanCombo.setCurrentIndex(self.mapping.green)
            self.blueChanCombo.setCurrentIndex(self.mapping.blue)
            self.setScrollBarsFromCanvas()
        # cache the image in case the mapping changes
        self.previmg = img
        # This will clear the screen if img is None
        self.redisplay()

    def redisplay(self):
        self.canvas.display(self.previmg, self.mapping)

    ## reset the canvas to x1 magnification
    def reset(self):
        self.canvas.reset()
        self.canvas.update()

    ## set the scroll bars from the position and zoom of the underlying canvas
    # first, we set the min and max of the bars to the pixel range, minus the size of the bar itself
    def setScrollBarsFromCanvas(self):
        self.scrollH.setMinimum(0)
        self.scrollV.setMinimum(0)
        img = self.canvas.img
        if img is not None:
            h, w = img.shape[:2]
            # work out the size of the scroll bar from the zoom factor
            hsize = w * self.canvas.zoomscale
            vsize = h * self.canvas.zoomscale
            self.scrollH.setPageStep(hsize)
            self.scrollV.setPageStep(vsize)
            # and set the actual scroll bar size
            self.scrollH.setMaximum(w - hsize)
            self.scrollV.setMaximum(h - vsize)
            # and the position
            self.scrollH.setValue(self.canvas.x)
            self.scrollV.setValue(self.canvas.y)

    ## vertical scrollbar handler   
    def vertScrollChanged(self, v):
        self.canvas.y = v
        self.canvas.update()

    ## horizontal scrollbar handler
    def horzScrollChanged(self, v):
        self.canvas.x = v
        self.canvas.update()
