"""Canvas widget for showing a CV image"""
import logging
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union, List, Tuple, Dict

import cv2 as cv
import numpy as np
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt, QSize, QTimer
from PySide2.QtGui import QImage, QPainter, QBitmap, QCursor, QPen, QKeyEvent
from PySide2.QtWidgets import QCheckBox, QMessageBox, QMenu

import pcot
import pcot.ui as ui
from pcot import imageexport, canvasnormalise, dq
from pcot.datum import Datum
from pcot.ui import canvasdq
from pcot.ui.canvasdq import CanvasDQSpec
from pcot.ui.collapser import Collapser, CollapserSection
from pcot.ui.spectrumwidget import SpectrumWidget
import pcot.dq
from pcot.utils.deb import Timer

if TYPE_CHECKING:
    from pcot.xform import XFormGraph, XForm

logger = logging.getLogger(__name__)

# how many DQ overlays we can have
NUMDQS = 3


class PersistBlock:
    """This is the block owned by a node which has a canvas, to store data which is persisted
    for the canvas only."""
    showROIs: bool  # should we show all ROIs and not just the ones defined in this node?
    normToCropped: bool  # boolean, should we normalise to only the visible part of the image?
    normMode: int  # normalisation mode e.g. NormToRGB, see canvasnormalise.py
    dqs: List[CanvasDQSpec]  # settings for each DQ layer

    def __init__(self, d=None):
        """sets default values, or perform the inverse of serialise(), turning the serialisable form into one
        of these objects"""
        if d is None:
            self.showROIs = True
            self.dqs = [CanvasDQSpec(showBad=(x == 0)) for x in range(NUMDQS)]  # 3 of these set to defaults
            self.normToCropped = False
            self.normMode = canvasnormalise.NormToImg
        else:
            self.showROIs, self.normMode, self.normToCropped, dqs = d
            self.normMode = int(self.normMode)  # deal with legacy files
            self.normToCropped = bool(self.normToCropped)
            self.dqs = [CanvasDQSpec(d) for d in dqs]

    def serialise(self):
        """return a version of this type which can be serialised into JSON"""
        dqs = [d.serialise() for d in self.dqs]
        return [self.showROIs, self.normMode, self.normToCropped, dqs]


# the actual drawing widget, contained within the Canvas widget
class InnerCanvas(QtWidgets.QWidget):
    # the numpy image we are rendering, having been converted to RGB
    rgb: Optional[np.ndarray]
    # the imagecube we are rendering, from which the above is generated
    imgCube: Optional['ImageCube']
    # the text that appears at bottom of the image
    desc: str
    # our main Canvas widget, which contains this widget
    canv: 'Canvas'
    # the current zoom level: 1 to contain the entire image onscreen
    zoomscale: float
    # defines the zoom factor which scales the canvas to hold the image
    scale: float
    # coords of top left pixel in canvas
    x: float
    y: float
    # cursor coords in image space
    cursorX: float
    cursorY: float
    # the size of that part of the image which is in view
    cutw: int
    cuth: int

    cursor = None  # custom cursor; created once on first use

    def __init__(self, canv, parent=None):
        super().__init__(parent)
        self.rgb = None
        self.imgCube = None
        self.desc = ""
        self.zoomscale = 1
        self.scale = 1
        self.cursorX = 0  # coords of cursor in image space
        self.cursorY = 0

        self.x = 0  # coords of top left of img in view
        self.y = 0
        self.cutw = 0  # size of image in view
        self.cuth = 0
        self.panning = False
        self.panX = None
        self.panY = None
        self.canv = canv
        self.timer = QTimer(self)

        # used to regularly redraw the canvas if elements are flashing
        self.redrawOnTick = False
        self.flashCycle = True
        self.timer.timeout.connect(self.tick)
        self.timer.start(300)  # flash rate

        # needs to do this to get key events
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.setCursor(InnerCanvas.getCursor())
        self.setMouseTracking(True)  # so we get move events with no button press
        self.reset()

    def img2qimage(self, img):
        """convert a cv/numpy image to a Qt image. input must be 3 channels, 0-1 floats.
        Ugly attempt at a hack - there appears to be a bug in Pyside whereby the underlying
        image is a temporary but Qt thinks it's permanent. This bug will be fixed in Pyside 5.15.4 -
        I think it's this: https://bugreports.qt.io/browse/PYSIDE-1563

        Workaround - stash the original image in a field so it sticks around.

        Repro: set an input. Set a rect on the input. Set an expr on the rect (I use a*0.5).
        Click around, opening and closing tabs in various ways.
        """
        self.origimg = (img * 256).clip(max=255).astype(np.ubyte)
        height, width, channel = self.origimg.shape
        assert channel == 3
        bytesPerLine = 3 * width
        return QImage(self.origimg.data, width, height,
                      bytesPerLine, QImage.Format_RGB888)

    @classmethod
    def getCursor(cls):
        """Get the custom cursor, creating it if necessary as a class attribute"""
        if cls.cursor is None:
            bm = QBitmap(32, 32)
            CROSSHAIRLENTHICK = 4
            CROSSHAIRLENTHIN = 10
            bm.clear()
            ptr = QPainter(bm)
            p = QPen()
            p.setWidth(3)
            ptr.setPen(p)
            ptr.drawLine(0, 16, CROSSHAIRLENTHICK, 16)
            ptr.drawLine(31, 16, 31 - CROSSHAIRLENTHICK, 16)
            ptr.drawLine(16, 0, 16, CROSSHAIRLENTHICK)
            ptr.drawLine(16, 31, 16, 31 - CROSSHAIRLENTHICK)

            p.setWidth(1)
            ptr.setPen(p)
            ptr.drawLine(0, 16, CROSSHAIRLENTHIN, 16)
            ptr.drawLine(31, 16, 31 - CROSSHAIRLENTHIN, 16)
            ptr.drawLine(16, 0, 16, CROSSHAIRLENTHIN)
            ptr.drawLine(16, 31, 16, 31 - CROSSHAIRLENTHIN)
            ptr.drawPoint(16, 16)

            ptr.end()
            # BM and MASK work like this:
            # B=0 M=0 gives transparent
            # B=0 M=1 gives white
            # B=1 M=1 gives black
            # B=1 M=0 is XOR under Windows, but undefined elsewhere!
            if platform.system() == 'Windows':
                # we want to use XOR under windows
                mask = QBitmap(32, 32)
                mask.clear()
            else:
                # on other platforms we want white on transparent.
                mask = bm  # gives white
                bm = QBitmap(32, 32)
                bm.clear()

            cls.cursor = QCursor(bm, mask, 16, 16)
        return cls.cursor

    ## resets the canvas to zoom level 1, top left pan
    def reset(self):
        # not the same as self.scale, which defines the scale of the image 
        # to fit in the on-screen window at 1x resolution.
        self.zoomscale = 1
        # pixel at top-left of visible image within window (when zoomed)
        self.x = 0
        self.y = 0

    def tick(self):
        """Timer tick"""
        if self.redrawOnTick:
            self.flashCycle = 1 - self.flashCycle
            self.update()

    ## returns the graph this canvas is part of
    def getGraph(self):
        return self.canv.graph

    def display(self, img: 'ImageCube', isPremapped: bool, ):
        """display an image next time paintEvent happens, and update to cause that.
        Will also handle None (by doing nothing)"""
        self.imgCube = img
        if img is not None:
            self.desc = img.getDesc(self.getGraph())

            if not isPremapped:
                # convert to RGB
                rgb = img.rgb()
                if rgb is None:
                    ui.error("Unusual - the RGB representation is None")
            else:
                rgb = img.img  # already done
                if img is None:
                    ui.error("Unusual - the image has no numpy array")

            # only reset the image zoom if the shape has changed
            # DISABLED so that image stitching is bearable.
            #            if self.img is None or self.img.shape[:2] != img.shape[:2]:
            #                self.reset()
            self.rgb = rgb
        else:
            self.rgb = None
            self.reset()
        self.update()

    def drawCursor(self, img, cutx, cuty):
        """"highlight the pixel under the cursor, but only if the cut canvas area is
        small enough that there's any point (it's a slow operation!)
        img: the "cut" region in the image; i.e. the part of the image being displayed.
        cutx,cuty: the top left of the 'cut' region in the image"""

        if min(self.cutw, self.cuth) < 200:
            curx, cury = self.cursorX - cutx, self.cursorY - cuty
            if 0 <= curx < self.cutw and 0 <= cury < self.cuth:
                img = img.copy()  # copy for drawing (to avoid trails)
                r, g, b = img[cury, curx, :]
                # we normally negate the point - but if it's too close to grey, do something else
                diff = max(abs(r - 0.5), abs(g - 0.5), abs(b - 0.5))
                if diff > 0.3:
                    img[cury, curx, :] = (1 - r, 1 - g, 1 - b)
                else:
                    img[cury, curx, :] = (1, 1, 1)  # too grey; replace with white

    ## the paint event
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(event.rect(), Qt.blue)
        widgw = self.size().width()  # widget dimensions
        widgh = self.size().height()
        # here self.img is a numpy image
        tt = Timer("paint", enabled=False)
        if self.rgb is not None:
            imgh, imgw = self.rgb.shape[0], self.rgb.shape[1]

            # work out the "base scale" so that a zoomscale of 1 fits the entire
            # image
            aspect = imgw / imgh
            if widgh * aspect > widgw:
                self.scale = imgw / widgw
            else:
                self.scale = imgh / widgh

            scale = self.getScale()

            # work out the size of the widget in image pixel coordinates
            cutw = int(widgw * scale)
            cuth = int(widgh * scale)
            # get the top-left coordinate and cut the area.            
            cutx = int(self.x)
            cuty = int(self.y)
            # get the viewable section of the RGB
            rgbcropped = self.rgb[cuty:cuty + cuth, cutx:cutx + cutw]
            tt.mark("rgb crop")

            # now get the size of the image that was actually cut (some areas may be out of range)
            self.cuth, self.cutw = rgbcropped.shape[:2]

            # This is where we normalise according to the current normalisation
            # scheme. We need to pass in the crop rectangle for finding the normalisation range in NormToImg mode.

            #            print(f"Norm Mode: {self.canv.canvaspersist.normMode} / {self.canv.canvaspersist.normToCropped}")
            rgbcropped = canvasnormalise.canvasNormalise(self.imgCube.img,
                                                         rgbcropped,
                                                         self.rgb,
                                                         self.canv.canvaspersist.normMode,
                                                         self.canv.canvaspersist.normToCropped,
                                                         (cutx, cuty, self.cutw, self.cuth))
            tt.mark("norm")
            # Here we draw the overlays and get any extra text required
            rgbcropped, dqtext = self.drawDQOverlays(rgbcropped, cutx, cuty, cutw, cuth)
            tt.mark("overlay")

            # draw the cursor crosshair into the image for accuracy
            self.drawCursor(rgbcropped, cutx, cuty)
            tt.mark("cursor")
            # now resize the cut area up to fit the widget and draw it. Using area interpolation here:
            # cubic produced odd artifacts on float images.
            rgbcropped = cv.resize(rgbcropped, dsize=(int(self.cutw / scale), int(self.cuth / scale)),
                                   interpolation=cv.INTER_AREA)
            tt.mark("resize")
            p.drawImage(0, 0, self.img2qimage(rgbcropped))
            tt.mark("draw image")

            # draw annotations (and ROIs, which are annotations too)
            # on the image

            if self.canv.canvaspersist.showROIs:
                # we're showing ALL rois
                rois = None
            elif self.canv.ROInode is not None:
                # this is a canvas for a node which generates ROIs, show only those (if showROIs is false)
                rois = self.canv.ROInode.type.getMyROIs(self.canv.ROInode)
            else:
                # don't show any ROIs if this isn't an ROI-generator and showROIs is false.
                rois = []

            p.save()
            p.scale(1 / self.getScale(), 1 / self.getScale())
            p.translate(-self.x, -self.y)
            # slightly mad chain of indirections to get the document alpha setting
            self.imgCube.drawAnnotationsAndROIs(p, onlyROI=rois, alpha=self.canv.graph.doc.settings.alpha / 100.0)
            p.restore()

            tt.mark("annotations")

            # now do any extra drawing onto the image itself.
            if self.canv.paintHook is not None:
                self.canv.paintHook.canvasPaintHook(p)

            tt.mark("hook")

            # and draw the descriptor
            p.setPen(Qt.yellow)
            p.setBrush(Qt.yellow)
            r = QtCore.QRect(0, widgh - 20, widgw, 20)
            p.drawText(r, Qt.AlignLeft, f"{self.desc} {dqtext}")
            tt.mark("descriptor")
        else:
            # there's nothing to draw
            self.scale = 1
        p.end()

    def drawDQOverlays(self, img, cutx, cuty, cutw, cuth) -> Tuple[np.ndarray, str]:
        """Draw the DQ overlays onto the RGB image img, which has already been cropped down to
        cutx,cuty,cutw,cuth. That cropping will need to be done on other data.

        It may be necessary to add code to handle missing / NA data. I'd rather not do that here
        for speed; we should just set the uncertainty to zero elsewhere for no data.

        We return the modified image and any extra text that gets tacked onto the descriptor"""

        txt = ""
        self.redrawOnTick = False

        if self.canv.isDQHidden:  # are DQs temporarily disabled?
            return img, txt

        t = Timer("DQ", enabled=False)
        for d in self.canv.canvaspersist.dqs:
            if d.isActive():
                if d.data == canvasdq.DTypeUnc or d.data == canvasdq.DTypeUncGtThresh or \
                        d.data == canvasdq.DTypeUncLtThresh:
                    # we're viewing uncertainty data, so cut out the relevant area
                    data = self.imgCube.uncertainty[cuty:cuty + cuth, cutx:cutx + cutw]
                    # and process it
                    if d.stype == canvasdq.STypeMaxAll:
                        # single-channel vs multichannel images.
                        if self.imgCube.channels > 1:
                            data = np.amax(data, axis=2)  # a bit slow
                    elif d.stype == canvasdq.STypeSumAll:
                        if self.imgCube.channels > 1:
                            data = np.sum(data, axis=2)  # a bit slot
                    else:
                        if self.imgCube.channels > 1:
                            data = data[:, :, d.channel]
                    # now we have the uncertainty data, threshold if that's what's wanted.
                    if d.data == canvasdq.DTypeUncGtThresh:
                        data = (data > d.thresh).astype(np.float32)
                    elif d.data == canvasdq.DTypeUncLtThresh:
                        data = (data < d.thresh).astype(np.float32)
                    else:
                        # otherwise normalize
                        mn = np.min(data)
                        rng = np.max(data) - mn
                        txt = f": RANGE {mn:0.3f}, {np.max(data):0.3f}"
                        if rng > 0.0000001:
                            data = (data - mn) / rng
                        else:
                            data = np.zeros(data.shape, dtype=float)

                elif d.data > 0:
                    # otherwise it's a DQ bit (or BAD dq bits), so cut that out
                    data = self.imgCube.dq[cuty:cuty + cuth, cutx:cutx + cutw]
                    t.mark("cut")
                    if self.imgCube.channels > 1:
                        # we can leave single channel images alone
                        if d.stype == canvasdq.STypeMaxAll or d.stype == canvasdq.STypeSumAll:
                            # union all channels
                            data = np.bitwise_or.reduce(data, axis=2)
                        else:
                            # or extract relevant channel
                            data = data[:, :, d.channel]
                    t.mark("or/extract")
                    # extract the relevant bit(s). This should work with BAD too, which would
                    # give a selection of bits. Remember that 'data' is a slice; we musn't
                    # modify it!
                    data = np.bitwise_and(data, d.data)
                    mask = data > 0  # which pixels have the bit set
                    t.mark("and")
                    # now convert that to float, setting nonzero to 1 and zero to 0.
                    data = mask.astype(np.float32)
                    t.mark("tofloat")
                # expand the data to RGB, but in different ways depending on the colour!
                r, g, b, flash = canvasdq.colours[d.col]
                if flash:
                    self.redrawOnTick = True
                # avoiding the creating of new arrays where we can.

                if not flash or self.flashCycle:
                    zeroes = np.zeros(data.shape, dtype=float)
                    data = data ** 2*d.contrast
                    t.mark("contrast")
                    # set the data opacity
                    data *= 1 - d.trans
                    t.mark("mult")
                    # here we 'tint' the data
                    r = data if r > 0.5 else zeroes
                    g = data if g > 0.5 else zeroes
                    b = data if b > 0.5 else zeroes
                    data = np.dstack((r, g, b))  # data is now RGB
                    # combine with image, avoiding copies.
                    t.mark("stack")
                    # additive or "normal" blending
                    if d.additive:
                        np.add(data, img, out=data)
                        t.mark("add")
                    else:
                        mask = np.dstack([mask, mask, mask]).astype(np.bool)
                        # img is the original image. Mask so only the bits we want to set get changed.
                        img = np.ma.masked_array(img, ~mask)
                        img *= d.trans
                        img += data
                        data = img.data  # remove mask
                        t.mark("blend")
                    # clip the data (mainly because of additive, but just in case other
                    # stuff has happened)
                    # The line below is faster than the standard np.clip(data, 0, 1, out=data)
                    # https://janhendrikewers.uk/exploring_faster_np_clip.html
                    np.core.umath.maximum(np.core.umath.minimum(data, 1), 0, out=data)
                    t.mark("clip")
                    img = data
        return img, txt

    def getScale(self):
        return self.scale * self.zoomscale

    ## given point in the widget, return coords in the image. Takes a QPoint or None; if the latter
    # we get the point under the cursor
    def getImgCoords(self, p: Optional[QtCore.QPoint] = None):
        if p is None:
            return self.cursorX, self.cursorY
        else:
            x = int(p.x() * (self.getScale()) + self.x)
            y = int(p.y() * (self.getScale()) + self.y)
            return x, y

    ## given a point in the image, give coordinates in the widget
    def getCanvasCoords(self, x, y):
        x = (x - self.x) / self.getScale()
        y = (y - self.y) / self.getScale()
        return x, y

    def keyPressEvent(self, e: QKeyEvent):
        if self.canv.keyHook is not None:
            self.canv.keyHook.canvasKeyPressEvent(e)
        return super().keyPressEvent(e)

    ## mouse press handler, can delegate to a hook
    def mousePressEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        if e.button() == Qt.MidButton:
            self.panning = True
            self.panX, self.panY = x, y
        elif self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMousePressEvent(x, y, e)
        return super().mousePressEvent(e)

    ## mouse move handler, can delegate to a hook
    def mouseMoveEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        self.cursorX, self.cursorY = x, y
        if self.panning:
            dx = x - self.panX
            dy = y - self.panY
            self.x -= dx * 0.5
            self.y -= dy * 0.5
            self.x = max(0, min(self.x, self.rgb.shape[1] - self.cutw))
            self.y = max(0, min(self.y, self.rgb.shape[0] - self.cuth))
            self.panX, self.panY = x, y
        else:
            self.canv.mouseMove(x, y, e)
        self.update()
        return super().mouseMoveEvent(e)

    ## mouse release handler, can delegate to a hook
    def mouseReleaseEvent(self, e):
        x, y = self.getImgCoords(e.pos())
        if e.button() == Qt.MidButton:
            self.panning = False
        elif self.canv.mouseHook is not None:
            self.canv.mouseHook.canvasMouseReleaseEvent(x, y, e)
        return super().mouseReleaseEvent(e)

    ## mouse wheel handler, changes zoom
    def wheelEvent(self, e):
        # get the mousepos in the image and calculate the new zoom
        wheel = 1 if e.angleDelta().y() < 0 else -1
        # x,y here is the zoom point
        x, y = self.getImgCoords(e.pos())
        newzoom = self.zoomscale * math.exp(wheel * 0.2)

        # can't zoom when there's no image
        if self.rgb is None:
            return

        # get image coords, and clip the event's coords to those
        # (to make sure we're not clicking on the background of the canvas)
        imgh, imgw = self.rgb.shape[0], self.rgb.shape[1]
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
        self.cursorX, self.cursorY = self.getImgCoords(e.pos())
        self.update()


def makesidebarLabel(t):
    lab = QtWidgets.QLabel(t)
    lab.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
    return lab


class Canvas(QtWidgets.QWidget):
    """Canvas : a widget for drawing multispectral ImageCube data. Consists of InnerCanvas (the image as RGB),
    scrollbars and extra controls."""

    ## @var paintHook
    # an object with a paintEvent() which can do extra drawing (or None)
    paintHook: Optional[object]

    ## @var mouseHook
    # an object with a set of mouse events for handling clicks and moves (or None)
    mouseHook: Optional[object]

    ## @var keyHook
    # an object with an event for key handling
    keyHook: Optional[object]

    ## @var graph
    # the graph of which I am a part. Not really optional, but I have to set it after construction.
    graph: Optional['XFormGraph']

    ## @var mapping
    # the mapping we are editing, and using to display/generate the RGB representation. Unless we're in 'alreadyRGBMapped'
    # in which case it's just a mapping we are editing - we display an image mapped elsewhere. Again, not actually
    # optional - we have to set it in the containing window's init.
    mapping: Optional['ChannelMapping']

    ## @var previmg
    # previous image, so we can avoid redisplay.
    previmg: Optional['ImageCube']

    ## @var nodeToUIChange
    # Node to do a UI change on whenever we redisplay an image (the mapping may have changed, and in the case of premapped
    # images it's the node that applies the mapping)
    nodeToUIChange: Optional['XForm']

    ## @var isPremapped
    # is this a premapped image?
    isPremapped: bool

    ## @var canvas
    # the actual canvas itself on which the image is displayed
    canvas: InnerCanvas

    ## @var ROInode
    # if we're displaying the canvas of an ROI node, a reference to that node
    # so we can display stats for just its ROI. Otherwise None.
    ROInode: Optional['XForm']

    # the DQ display data
    dqs: List[CanvasDQSpec]

    # is the DQ data hidden?
    isDQHidden: bool

    # List of the DQ section widgets
    dqSections: List[CollapserSection]

    ## constructor
    def __init__(self, parent):
        super().__init__(parent)
        self.firstDisplayDone = False
        self.paintHook = None
        self.mouseHook = None
        self.keyHook = None
        self.graph = None
        self.nodeToUIChange = None
        self.ROInode = None
        self.isDQHidden = False  # does not persist!
        self.recursing = False  # An ugly hack to avoid recursion in ROI nodes
        self.dqSourceCache = [None for i in range(NUMDQS)]  # source name cache for each channel
        # outer layout is a horizontal box - the sidebar and canvas+scrollbars are in this
        outerlayout = QtWidgets.QHBoxLayout()
        self.setLayout(outerlayout)
        # by default we don't have a persister node, so we persist data privately (i.e. not at all).
        # If we set a persister we use a persist block in that. I'm tempted to set this to None because
        # really we should always have a persister!
        self.canvaspersist = PersistBlock()

        # Sidebar widgets.

        self.collapser = Collapser()
        self.collapser.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                     QtWidgets.QSizePolicy.MinimumExpanding)

        outerlayout.addWidget(self.collapser)
        outerlayout.setAlignment(Qt.AlignTop)

        # create the widgets that go inside the collapser
        self.dqSections = []
        self.createWidgets()
        self.collapser.end()

        splitter = QtWidgets.QSplitter()
        splitter.setHandleWidth(10)
        outerlayout.addWidget(splitter)

        innercanvasContainer = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        innercanvasContainer.setLayout(layout)
        innercanvasContainer.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )
        splitter.addWidget(innercanvasContainer)
        outerlayout.setContentsMargins(0, 0, 0, 0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.spectrumWidget = SpectrumWidget()
        self.spectrumWidget.setMinimumSize(300, 300)
        self.spectrumWidget.setMaximumWidth(600)
        self.spectrumWidget.setHidden(True)
        splitter.addWidget(self.spectrumWidget)

        ## now the canvas and scrollbars

        self.canvas = InnerCanvas(self)
        layout.addWidget(self.canvas, 0, 0)
        # layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        self.scrollV = QtWidgets.QScrollBar(Qt.Vertical)
        self.scrollV.valueChanged.connect(self.vertScrollChanged)
        layout.addWidget(self.scrollV, 0, 1)

        self.scrollH = QtWidgets.QScrollBar(Qt.Horizontal)
        self.scrollH.valueChanged.connect(self.horzScrollChanged)
        layout.addWidget(self.scrollH, 1, 0)

        self.resetButton = QtWidgets.QPushButton()
        self.resetButton.setMaximumWidth(20)
        layout.addWidget(self.resetButton, 1, 1)
        self.resetButton.clicked.connect(self.reset)

        # the mapping we are using - the image owns this, we just get a ref. when
        # the tab is created
        self.mapping = None
        # previous image (in case mapping changes and we need to redisplay the old image with a new mapping)
        self.previmg = None
        self.isPremapped = False

        pcot.ui.decorateSplitter(splitter, 1)

    def createWidgets(self):
        # These widgets are "hideable" in that we might not show them when we don't need to, e.g. for a single-channel
        # or RGB image. This isn't actually used at the moment, but could be. We add them into their own widget
        # with its own layout, and then that widget is added to a single-widget layout which is what gets set in the
        # collapser. Necessary because the collapser takes layouts.

        self.hideablebuttons = QtWidgets.QWidget()
        self.hideablebuttons.setContentsMargins(0, 0, 0, 0)

        hideable = QtWidgets.QGridLayout()
        hideable.setContentsMargins(3, 10, 3, 10)  # LTRB
        # these are the actual widgets specifying which channel in the cube is viewed.
        # We need to deal with these carefully.
        hideable.addWidget(makesidebarLabel("R"), 0, 0)
        self.redChanCombo = QtWidgets.QComboBox()
        self.redChanCombo.currentIndexChanged.connect(self.redIndexChanged)
        hideable.addWidget(self.redChanCombo, 0, 1)

        hideable.addWidget(makesidebarLabel("G"), 1, 0)
        self.greenChanCombo = QtWidgets.QComboBox()
        self.greenChanCombo.currentIndexChanged.connect(self.greenIndexChanged)
        hideable.addWidget(self.greenChanCombo, 1, 1)

        hideable.addWidget(makesidebarLabel("B"), 2, 0)
        self.blueChanCombo = QtWidgets.QComboBox()
        self.blueChanCombo.currentIndexChanged.connect(self.blueIndexChanged)
        hideable.addWidget(self.blueChanCombo, 2, 1)

        self.resetMapButton = QtWidgets.QPushButton("Guess RGB")
        hideable.addWidget(self.resetMapButton, 3, 0, 1, 2)
        self.resetMapButton.clicked.connect(self.resetMapButtonClicked)

        self.hideablebuttons.setLayout(hideable)  # add layout to widget
        self.blueChanCombo.setMinimumWidth(100)
        hideableLayout = QtWidgets.QVBoxLayout()  # make a single-widget layout
        hideableLayout.setContentsMargins(0, 0, 0, 0)
        hideableLayout.addWidget(self.hideablebuttons)  # add the widget to it
        # add that layout to the collapser
        self.collapser.addSection("hideable", hideableLayout, isAlwaysOpen=True)

        # next section

        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(3, 10, 3, 10)  # LTRB

        self.badpixels = QtWidgets.QLabel('')
        self.badpixels.setStyleSheet("QLabel { background-color : white; color : red; }")
        self.badpixels.setVisible(False)
        layout.addWidget(self.badpixels, 1, 0, 1, 2)

        # self.roiToggle = TextToggleButton("ROIs", "ROIs")
        self.roiToggle = QCheckBox("ROIs")
        layout.addWidget(self.roiToggle, 2, 0)
        self.roiToggle.toggled.connect(self.roiToggleChanged)

        # self.spectrumToggle = TextToggleButton("Spectrum", "Spectrum")
        self.spectrumToggle = QCheckBox("spectrum")
        layout.addWidget(self.spectrumToggle, 2, 1)
        self.spectrumToggle.toggled.connect(self.spectrumToggleChanged)

        self.coordsText = QtWidgets.QLabel('')
        layout.addWidget(self.coordsText, 3, 0, 1, 2)

        self.roiText = QtWidgets.QLabel('')
        layout.addWidget(self.roiText, 4, 0, 1, 2)

        self.dimensions = QtWidgets.QLabel('')
        layout.addWidget(self.dimensions, 5, 0, 1, 2)

        self.hideDQ = QtWidgets.QCheckBox("hide DQ")
        layout.addWidget(self.hideDQ, 6, 0, 1, 2)
        self.hideDQ.toggled.connect(self.hideDQChanged)

        self.collapser.addSection("data", layout, isOpen=True)

        # normalisation section

        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(3, 10, 3, 10)  # LTRB

        ll = QtWidgets.QLabel("norm")
        layout.addWidget(ll, 0, 0)
        self.normComboBox = QtWidgets.QComboBox()
        self.normComboBox.addItem("to RGB", userData=canvasnormalise.NormToRGB)
        self.normComboBox.addItem("independent", userData=canvasnormalise.NormSeparately)
        self.normComboBox.addItem("to all bands", userData=canvasnormalise.NormToImg)
        self.normComboBox.addItem("none", userData=canvasnormalise.NormNone)
        self.normComboBox.currentIndexChanged.connect(self.normChanged)
        layout.addWidget(self.normComboBox, 0, 1)

        self.normCroppedCheckBox = QtWidgets.QCheckBox("to cropped area")
        self.normCroppedCheckBox.toggled.connect(self.normChanged)
        layout.addWidget(self.normCroppedCheckBox, 1, 0, 1, 2)

        self.collapser.addSection("normalisation", layout, isOpen=False)

        # DQ sections(s)

        self.dqwidgets = self.createDQWidgets(self.collapser)

    def createDQWidgets(self, collapser) -> List[Dict]:
        """Create the DQ overlay controls and store the widgets in a list of NUMDQS dicts.
        Takes the collapser to add the controls to; each one gets a section.
        (see below). Returns the list of dicts."""

        # this will end up as a list of dictionaries, one for each overlay. Each dict has:
        #  source: the source channel combo box (which must include MaxAll and SumAll as well as channels)
        #  data: the data combo box for the data type (DQ bit, uncertainty... or None)
        #  col: the colour of the overlay

        dqwidgets = []

        for i in range(NUMDQS):
            row = dict()  # create and add the (empty as yet) dict
            dqwidgets.append(row)

            layout = QtWidgets.QGridLayout()
            layout.setContentsMargins(3, 10, 3, 10)  # LTRB
            layout.setHorizontalSpacing(0)
            layout.setVerticalSpacing(0)

            sourcecb = QtWidgets.QComboBox()  # leave empty for now
            sourcecb.addItem("this is a test value")  # BEWARE LONG STRINGS IN HERE!
            sourcecb.setMinimumContentsLength(5)
            layout.addWidget(QtWidgets.QLabel("SRC"), 0, 0)
            layout.addWidget(sourcecb, 0, 1)
            row['source'] = sourcecb

            datacb = QtWidgets.QComboBox()
            for name, val in CanvasDQSpec.getDataItems():
                # note - these are integers, although they might be uint16 at source. When we do
                # findData later we look for them as ints.
                datacb.addItem(name, userData=int(val))
            layout.addWidget(QtWidgets.QLabel("DATA"), 1, 0)
            layout.addWidget(datacb, 1, 1)
            row['data'] = datacb

            colcb = QtWidgets.QComboBox()
            for x in canvasdq.colours:
                colcb.addItem(x)
            layout.addWidget(QtWidgets.QLabel("COL"), 2, 0)
            layout.addWidget(colcb, 2, 1)
            row['col'] = colcb

            #            for widget in row.values():  # adjust each combobox
            #                widget.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

            # sliders etc
            ll = QtWidgets.QLabel("transp")
            layout.addWidget(ll, 3, 0)
            transSlider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
            layout.addWidget(transSlider, 3, 1)
            row['trans'] = transSlider

            ll = QtWidgets.QLabel("contrast")
            layout.addWidget(ll, 4, 0)
            contrastSlider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
            layout.addWidget(contrastSlider, 4, 1)
            row['contrast'] = contrastSlider

            ll = QtWidgets.QLabel("thresh")
            layout.addWidget(ll, 5, 0)
            threshBox = QtWidgets.QDoubleSpinBox()
            threshBox.setMaximum(9.99)
            threshBox.setStepType(QtWidgets.QDoubleSpinBox.AdaptiveDecimalStepType)
            layout.addWidget(threshBox, 5, 1)
            row['thresh'] = threshBox

            ll = QtWidgets.QLabel("additive")
            layout.addWidget(ll, 6, 0)
            additive = QtWidgets.QCheckBox()
            layout.addWidget(additive, 6, 1)
            row['additive'] = additive

            colcb.currentIndexChanged.connect(lambda _: self.dqWidgetChanged())
            datacb.currentIndexChanged.connect(lambda _: self.dqWidgetChanged())
            sourcecb.currentIndexChanged.connect(lambda _: self.dqWidgetChanged())

            transSlider.sliderReleased.connect(self.dqWidgetChanged)
            contrastSlider.sliderReleased.connect(self.dqWidgetChanged)
            threshBox.valueChanged.connect(lambda _: self.dqWidgetChanged())
            additive.stateChanged.connect(lambda _: self.dqWidgetChanged())

            self.dqSections.append(collapser.addSection(f"DQ layer {i}", layout))

        return dqwidgets

    def dqWidgetChanged(self):
        if not self.recursing:  # avoid programmatic changes messing things up
            self.recursing = True
            self.getDQWidgetState()
            self.recursing = False
            self.redisplay()

    def contextMenuEvent(self, ev: QtGui.QContextMenuEvent) -> None:
        super().contextMenuEvent(ev)   # run the super's menu, which will run any item's menu
        if not ev.isAccepted():        # if the event wasn't accepted, run our menu
            menu = QMenu()
            export = menu.addAction("Export as PDF, PNG or SVG")
            save = menu.addAction("Save as PARC (PCOT datum archive)")
            a = menu.exec_(ev.globalPos())

            if a == export:
                self.exportAction()
            elif a == save:
                self.saveAction()


    def ensureDQValid(self):
        """Make sure the DQ data is valid for the image if present; if not reset to None"""
        for i, d in enumerate(self.canvaspersist.dqs):
            if d.stype == canvasdq.STypeChannel:
                if self.previmg is None or d.channel >= self.previmg.channels:
                    print("ENSURE DQ VALID OVERRIDE")
                    d.stype = canvasdq.STypeMaxAll
                    d.data = canvasdq.DTypeNone

    def setDQWidgetState(self):
        """Set the DQ table widget state to the DQ specs stored in this canvas. Also may repopulate
        the source combo because channels may have changed.
        """

        old = self.recursing
        self.recursing = True

        self.ensureDQValid()  # first, make sure the data is valid
        for i, d in enumerate(self.canvaspersist.dqs):
            w = self.dqwidgets[i]  # get the dictionary holding the widgets for this DQ block

            # first, make sure the source combo box is correctly populated.
            # We should have a list of brief source names for each channel.
            # If this is empty or changed, we repopulate.

            # first build a list of the source names
            if self.previmg is not None:
                sources = [s.brief(captionType=self.graph.doc.settings.captionType)
                           for s in self.previmg.sources.sourceSets]
            else:
                sources = []

            # and compare with the cached list of source names. If not the same, repopulate
            sourcecombo = w['source']
            if sources != self.dqSourceCache[i]:
                self.dqSourceCache[i] = sources
                sourcecombo.clear()
                sourcecombo.addItem("max", userData='maxall')
                sourcecombo.addItem("sum", userData='sumall')
                if self.previmg is not None:
                    for chanidx, brief in enumerate(sources):
                        sourcecombo.addItem(f"{chanidx}) {brief}", userData=chanidx)

            # then select the source - if it's not found (perhaps a channel disappeared) we'll
            # get a sourceItemIdx<0, but that should never happen.
            if d.stype == canvasdq.STypeMaxAll:
                val = 'maxall'
            elif d.stype == canvasdq.STypeSumAll:
                val = 'sumall'
            elif d.stype == canvasdq.STypeChannel:
                val = d.channel
            sourceItemIdx = sourcecombo.findData(val)

            if sourceItemIdx >= 0:
                sourcecombo.setCurrentIndex(sourceItemIdx)
            else:
                # override if we couldn't find a channel - that shouldn't happen because we
                # called ensureDQValid
                sourcecombo.setCurrentIndex(sourcecombo.findData('maxall'))
                ui.error(f"invalid channel {d.channel} in DQ source combo box")

            # Now the data type
            datacombo = w['data']
            # the d.data field is likely to be a uint16 if it represents a bit or bitmask. We need to
            # convert to an int, because that's how they all get added to the combobox.
            dataidx = datacombo.findData(int(d.data))

            if dataidx >= 0:
                datacombo.setCurrentIndex(dataidx)
            else:
                ui.error(f"Can't find data value {d.data} in data combo for canvas DQ overlay")

            # and colour data
            colcombo = w['col']
            colidx = colcombo.findText(d.col)
            if colidx >= 0:
                colcombo.setCurrentIndex(colidx)
            else:
                ui.error(f"Can't find colour value {d.col} in colour combo for canvas DQ overlay")

            # finally the sliders etc.
            w['trans'].setValue(int(d.trans * 99))
            w['contrast'].setValue(int(d.contrast * 99))
            w['thresh'].setValue(d.thresh)
            w['additive'].setChecked(d.additive)

        self.recursing = old

    def getDQWidgetState(self):
        """Can't think of a better name at the moment - this regenerates the dqs (CanvasDQSpec list)
        from the DQ widgets. It assumes those objects already exist, so we just modify them."""

        for i, d in enumerate(self.canvaspersist.dqs):
            w = self.dqwidgets[i]  # get the dictionary holding the widgets for this DQ block
            # first set the dq source from the source widget data
            sourcedata = w['source'].currentData()
            if sourcedata == 'maxall':
                d.stype = canvasdq.STypeMaxAll
            elif sourcedata == 'sumall':
                d.stype = canvasdq.STypeSumAll
            else:
                d.stype = canvasdq.STypeChannel
                d.channel = sourcedata

            # then the 'data' field; this goes directly in
            d.data = w['data'].currentData()

            # as does the colour field (from 'text' this time)
            d.col = w['col'].currentText()

            # the sliders etc.
            d.trans = float(w['trans'].value()) / 99.0
            d.contrast = float(w['contrast'].value()) / 99.0
            d.thresh = w['thresh'].value()
            d.additive = w['additive'].isChecked()

        self.ensureDQValid()

    def mouseMove(self, x, y, event):
        self.coordsText.setText(f"{x},{y}")
        self.showSpectrum()
        if self.mouseHook is not None:
            self.mouseHook.canvasMouseMoveEvent(x, y, event)

    ## call this if this is only ever going to display single channel images
    # or annotated RGB images (obviating the need for source drop-downs). Actually
    # not used at the moment.
    def hideMapping(self):
        self.hideablebuttons.setVisible(False)

    ## this works by setting a data structure which is persisted, and holds some of our
    # data rather than us. Ugly, yes.
    def setPersister(self, p):
        self.canvaspersist = p.canvaspersist
        self.roiToggle.setEnabled(True)
        old = self.recursing
        self.recursing = True
        self.roiToggle.setChecked(p.canvaspersist.showROIs)
        self.normCroppedCheckBox.setChecked(p.canvaspersist.normToCropped)
        i = self.normComboBox.findData(self.canvaspersist.normMode)
        self.normComboBox.setCurrentIndex(i)
        self.recursing = old

    ## if this is a canvas for an ROI node, set that node.
    def setROINode(self, n):
        self.ROInode = n

    ## some canvas persistence data is to be stored from an object into a dict.
    # Get the data from the object and store it in the dict.
    @staticmethod
    def serialise(o, data):
        data['canvas'] = o.canvaspersist.serialise()

    ## inverse of setPersistData, done when we deserialise something
    @staticmethod
    def deserialise(o, data):
        o.canvaspersist = PersistBlock(data.get('canvas', None))

    ## prepare an object for holding some of our data
    @staticmethod
    def initPersistData(o):
        if not hasattr(o, 'persist'):
            o.canvaspersist = PersistBlock()

    # these sets a reference to the mapping this canvas is using - bear in mind this class can mutate
    # that mapping!
    def setMapping(self, mapping):
        self.mapping = mapping

    def resetMapButtonClicked(self):
        if self.previmg is not None:
            self.previmg.defaultMapping = None  # force a guess even if there is a default mat
            self.previmg.mapping.generateMappingFromDefaultOrGuess(self.previmg)
        self.redisplay()
        self.updateChannelSelections()

    # set the graph I'm part of
    def setGraph(self, g):
        self.graph = g

    def redIndexChanged(self, i):
        logger.debug(f"RED CHANGED TO {i}")
        self.mapping.red = i
        self.redisplay()

    def greenIndexChanged(self, i):
        logger.debug(f"GREEN CHANGED TO {i}")
        self.mapping.green = i
        self.redisplay()

    def blueIndexChanged(self, i):
        logger.debug(f"GREEN CHANGED TO {i}")
        self.mapping.blue = i
        self.redisplay()

    def roiToggleChanged(self, v):
        # can only work when a persister is there; if there isn't, will crash.
        # Hopefully we can disable the toggle.
        self.canvaspersist.showROIs = v
        self.redisplay()

    def normChanged(self):
        if not self.recursing:
            self.canvaspersist.normToCropped = self.normCroppedCheckBox.isChecked()
            self.canvaspersist.normMode = self.normComboBox.currentData()
            self.redisplay()

    def spectrumToggleChanged(self, v):
        self.spectrumWidget.setHidden(not v)

    def hideDQChanged(self, v):
        self.isDQHidden = self.hideDQ.isChecked()
        for x in self.dqSections:
            x.setVisible(not self.isDQHidden)
        self.redisplay()

    def exportAction(self):
        if self.previmg is None:
            return
        res = QtWidgets.QFileDialog.getSaveFileName(self,
                                                    'Save RGB image as PNG (without annotations)',
                                                    os.path.expanduser(pcot.config.getDefaultDir('savedimages')),
                                                    "PDF files (*.pdf) ;; PNG files (*.png)  ;; SVG files (*.svg)",
                                                    options=pcot.config.getFileDialogOptions()
                                                    )
        if res[0] != '':
            path, filt = res
            (_, ext) = os.path.splitext(path)
            pcot.config.setDefaultDir('savedimages', os.path.split(path)[0])
            ext = ext.lower()
            if ext == '':
                QMessageBox.critical(self, 'Error', "Filename should have an extension.")
            elif ext == '.png':
                r = QMessageBox.question(self, "Export to PNG", "Save with annotations?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if r == QMessageBox.No:
                    self.previmg.rgbWrite(path)
                    ui.log(f"Image written to {path}")
                elif r == QMessageBox.Yes:
                    imageexport.exportRaster(self.previmg, path)
                else:
                    ui.log("Export cancelled")
            elif ext == '.pdf':
                imageexport.exportPDF(self.previmg, path)
                ui.log(f"Image and annotations exported to {path}")
            elif ext == '.svg':
                imageexport.exportSVG(self.previmg, path)
            else:
                QMessageBox.critical(self, 'Error', "Filename has a strange extension.")
                ui.log(ext)

    def saveAction(self):
        """Save to a PARC file - a DatumStore with only one item in it."""
        if self.previmg is None:
            return
        res = QtWidgets.QFileDialog.getSaveFileName(self,
                                                    'Save as PARC',
                                                    os.path.expanduser(pcot.config.getDefaultDir('savedimages')),
                                                    "Datum Archive files (*.parc)",
                                                    options=pcot.config.getFileDialogOptions()
                                                    )
        if res[0] != '':

            desc, ok = QtWidgets.QInputDialog.getText(self,"Description",
                                                     "Enter text description (optional):",
                                                     QtWidgets.QLineEdit.Normal,
                                                     "")
            if not ok:
                desc = ''
            path, filt = res
            (root, ext) = os.path.splitext(path)
            pcot.config.setDefaultDir('savedimages', os.path.split(path)[0])
            ext = ext.lower()
            if ext == '':
                ext = '.parc'
            if ext == '.parc':
                from pcot.utils.datumstore import writeParc

                path = root + ext
                writeParc(path, Datum(Datum.IMG, self.previmg), description=desc)
            else:
                QMessageBox.critical(self, 'Error', "Filename has a strange extension.")
                ui.log(ext)

    ## this initialises a combo box, setting the possible values to be the channels in the image
    # input
    def addChannelsToChannelCombo(self, combo: QtWidgets.QComboBox, img: 'ImageCube'):
        combo.clear()
        for i in range(0, img.channels):
            # adds descriptor string and integer channels index
            cap = self.graph.doc.settings.captionType
            s = f"{i}) {img.sources.sourceSets[i].brief(cap)}"
            combo.addItem(s)

    def setCombosToImageChannels(self, img):
        self.addChannelsToChannelCombo(self.redChanCombo, img)
        self.addChannelsToChannelCombo(self.greenChanCombo, img)
        self.addChannelsToChannelCombo(self.blueChanCombo, img)

    def blockSignalsOnComboBoxes(self, b):
        self.redChanCombo.blockSignals(b)
        self.greenChanCombo.blockSignals(b)
        self.blueChanCombo.blockSignals(b)

    ## set this canvas (actually the InnerCanvas) to hold an image.
    # In the normal case (where the Canvas does the RGB mapping) just call with the image.
    # In the premapped case, call with the premapped RGB image, the source image, and the node.

    def display(self, img: Union[Datum, 'ImageCube'], alreadyRGBMappedImageSource=None, nodeToUIChange=None):
        self.firstDisplayDone = True

        if isinstance(img, Datum):
            img = img.get(Datum.IMG)  # if we are given a Datum, "unwrap" it
        if self.mapping is None:
            raise Exception(
                "Mapping not set in ui.canvas.Canvas.display() - should be done in tab's ctor with setMapping()")
        if self.graph is None:
            raise Exception(
                "Graph not set in ui.canvas.Canvas.display() - should be done in tab's ctor with setGraph()")
        if img is not None:
            # ensure there is a valid mapping (only do this if not already mapped)
            if alreadyRGBMappedImageSource is None:
                self.mapping.ensureValid(img)
            # now make the combo box options match the sources in the image
            # and finally make the selection each each box match the actual channel assignment
            self.blockSignalsOnComboBoxes(True)  # temporarily disable signals to avoid indexChanged calls
            # is this a premapped image? We need to remember that for redisplay()
            self.isPremapped = alreadyRGBMappedImageSource is not None
            self.setCombosToImageChannels(alreadyRGBMappedImageSource
                                          if alreadyRGBMappedImageSource is not None
                                          else img)
            self.redChanCombo.setCurrentIndex(self.mapping.red)
            self.greenChanCombo.setCurrentIndex(self.mapping.green)
            self.blueChanCombo.setCurrentIndex(self.mapping.blue)
            self.blockSignalsOnComboBoxes(False)  # and enable signals again
            self.setScrollBarsFromCanvas()
        # cache the image in case the mapping changes, and also for redisplay itself
        self.previmg = img
        # do this *after* setting the previmg
        self.setDQWidgetState()
        # When we're using a "premapped" image, whenever we redisplay, we'll have to recalculate the node:
        # when we change the mapping (which is why we would redisplay) it's the node code which regenerates
        # the remapped image.
        self.nodeToUIChange = nodeToUIChange
        # This will clear the screen if img is None
        self.redisplay()

    def updateChannelSelections(self):
        # update the channel selections in the combo boxes if they've been changed in code
        self.blockSignalsOnComboBoxes(True)  # temporarily disable signals to avoid indexChanged calls
        self.redChanCombo.setCurrentIndex(self.mapping.red)
        self.greenChanCombo.setCurrentIndex(self.mapping.green)
        self.blueChanCombo.setCurrentIndex(self.mapping.blue)
        self.blockSignalsOnComboBoxes(False)  # and enable signals again

    def redisplay(self):
        # similar to the below; avoid redisplay when we haven't displayed anything yet!
        if not self.firstDisplayDone:
            return
        # Note that we are doing ugly things to avoid recursion here. In some of the ROI nodes, this can happen:
        # updatetabs -> onNodeChanged -> display -> redisplay -> updatetabs...
        # This is the simplest way to avoid it.

        print(f"REDISPLAY of {self.previmg} with mapping {self.mapping}")
        if not self.recursing:
            self.recursing = True
            n = self.nodeToUIChange
            if n is not None:
                n.type.uichange(n)
                n.updateTabs()
            #            self.graph.performNodes(self.nodeToUIChange)
            self.recursing = False

        # set ROI pixel count text.
        if self.previmg is None:
            # if there's no image, then there are no pixels
            txt = ""
        elif self.canvaspersist.showROIs:
            # if we're displaying all ROIs, show that pixel count (and ROI count))
            txt = "{} pixels/{} ROIs".format(sum([x.pixels() for x in self.previmg.rois]),
                                             len(self.previmg.rois))
        elif self.ROInode is not None:
            # if there's an ROI being set from this node (and we're not showing all ROIs), show its details
            # Also have to check the ROI itself is OK (the method will do this)
            txt = self.ROInode.type.getROIDesc(self.ROInode)
        else:
            txt = ""
        self.roiText.setText(txt)

        # now image dimensions
        if self.previmg is None:
            txt = ""
        else:
            txt = f"{self.previmg.w} x {self.previmg.h} x {self.previmg.channels}"

        self.dimensions.setText(txt)

        # and bad pixels
        bp = 0 if self.previmg is None else self.previmg.countBadPixels()
        if bp > 0:
            self.badpixels.setVisible(True)
            self.badpixels.setText(f"{bp} BAD PIXELS")
        else:
            self.badpixels.setVisible(False)
            self.badpixels.setText("")

        self.canvas.display(self.previmg, self.isPremapped)
        self.setDQWidgetState()
        self.showSpectrum()

    ## reset the canvas to x1 magnification
    def reset(self):
        self.canvas.reset()
        self.canvas.update()
        self.showSpectrum()

    ## set the scroll bars from the position and zoom of the underlying canvas
    # first, we set the min and max of the bars to the pixel range, minus the size of the bar itself
    def setScrollBarsFromCanvas(self):
        self.scrollH.setMinimum(0)
        self.scrollV.setMinimum(0)
        rgb = self.canvas.rgb
        if rgb is not None:
            h, w = rgb.shape[:2]
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
        self.showSpectrum()

    ## horizontal scrollbar handler
    def horzScrollChanged(self, v):
        self.canvas.x = v
        self.canvas.update()
        self.showSpectrum()

    def getCanvasCoords(self, x, y):
        return self.canvas.getCanvasCoords(x, y)

    def getImgCoords(self, p):
        return self.canvas.getImgCoords(p)

    def showSpectrum(self):
        x, y = self.canvas.getImgCoords()
        if self.previmg is None:
            self.spectrumWidget.set(None, "No image in canvas")
            return
        if self.previmg.channels < 2:
            if 0 <= x < self.previmg.w and 0 <= y < self.previmg.h:
                val = self.previmg.img[y, x]
                unc = self.previmg.uncertainty[y, x]
                dqval = self.previmg.dq[y, x]
                dq = pcot.dq.names(dqval)
                self.spectrumWidget.set(None, f"Single channel:  {val:.3} +/- {unc:.3}. DQ:{dq} ({dqval})")
            return

        # within the coords, and multichannel image present

        if 0 <= x < self.previmg.w and 0 <= y < self.previmg.h and self.previmg.channels > 1:
            img = self.previmg
            pixel = img.img[y, x, :]  # get the pixel data
            pixuncs = img.uncertainty[y, x, :]
            pixdqs = img.dq[y, x, :]

            # build text string
            text = ""
            for i, ss in enumerate(img.sources):
                p = pixel[i]
                u = pixuncs[i]
                d = pixdqs[i]
                text += f"{i}) = {p:.3} +/- {u:.3} : {pcot.dq.names(d)} ({d}) {ss.brief()}\n"

            # get the channels which have a single wavelength
            # what do we do if they don't? I don't think you can display a spectrum!

            wavelengths = [img.wavelength(x) for x in range(img.channels)]

            goodWavelengths = [x for x in wavelengths if x > 0]
            chans = [x for x in range(img.channels) if wavelengths[x] > 0]

            # and get the data from the pixel which is for those wavelengths
            vals = [pixel[x] for x in chans]
            uncs = [pixuncs[x] for x in chans]
            dqs = [pixdqs[x] for x in chans]

            # now plot x=wavelengths,y=vals
            if len(vals) > 1:
                data = zip(goodWavelengths, vals, uncs, dqs)
            else:
                # but if there aren't enough data with wavelengths,
                # just show the values as text.
                text = "Cannot plot: no frequency data in channel sources\n" + text
                data = None
            self.spectrumWidget.set(data, text)

    def setNode(self, node):
        """This links fields in the canvas to fields in the node. We can't just have a `node` reference, because
        sometimes canvasses don't have nodes (inputs for example). And sometimes we only want to do part of this
        process, so the three different operations are available separately. But we have to do this in nodes before
        every redisplay, because the node may have been replaced by an undo operation."""

        self.setMapping(node.mapping)       # tell the canvas to use the node's RGB mapping
        self.setGraph(node.graph)           # tell the canvas what the graph is
        self.setPersister(node)             # and where it should store its data (ugly, yes).
