"""Canvas widget for showing a CV image"""
import logging
import math
import os
import platform
from typing import TYPE_CHECKING, Optional, Union

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QImage, QPainter, QBitmap, QCursor, QPen
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np
from PyQt5.QtWidgets import QCheckBox

import pcot
import pcot.ui as ui
from pcot.datum import Datum
from pcot.ui.specplot import SpecPlot
from pcot.ui.texttogglebutton import TextToggleButton

if TYPE_CHECKING:
    from pcot.xform import XFormGraph, XForm

logger = logging.getLogger(__name__)


def img2qimage(img):
    """convert a cv/numpy image to a Qt image
    input must be 3 channels, 0-1 floats
    """
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

    cursor = None  # custom cursor; created once on first use

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
                mask = bm   # gives white
                bm = QBitmap(32, 32)
                bm.clear()

            cls.cursor = QCursor(bm, mask, 16, 16)
        return cls.cursor

    ## constructor
    def __init__(self, canv, parent=None):
        super().__init__(parent)
        self.img = None
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
        # needs to do this to get key events
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.setCursor(InnerCanvas.getCursor())
        self.setMouseTracking(True)  # so we get move events with no button press
        self.reset()

    ## resets the canvas to zoom level 1, top left pan
    def reset(self):
        # not the same as self.scale, which defines the scale of the image 
        # to fit in the on-screen window at 1x resolution.
        self.zoomscale = 1
        # pixel at top-left of visible image within window (when zoomed)
        self.x = 0
        self.y = 0

    ## returns the graph this canvas is part of
    def getGraph(self):
        return self.canv.graph

    ## display an image next time paintEvent
    # happens, and update to cause that. Allow it to handle None too.
    def display(self, img: 'ImageCube', isPremapped: bool, showROIs: bool = False):
        if img is not None:
            self.desc = img.getDesc(self.getGraph())
            if not isPremapped:
                # convert to RGB
                img = img.rgb(showROIs=showROIs)  # convert to RGB
                if img is None:
                    ui.error("Unusual - the RGB representation is None")
            else:
                img = img.img  # already done
                if img is None:
                    ui.error("Unusual - the image has no numpy array")

            # only reset the image zoom if the shape has changed
            # DISABLED so that image stitching is bearable.
            #            if self.img is None or self.img.shape[:2] != img.shape[:2]:
            #                self.reset()
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

            scale = self.getScale()

            # work out the size of the widget in image pixel coordinates
            cutw = int(widgw * scale)
            cuth = int(widgh * scale)
            # get the top-left coordinate and cut the area.            
            cutx = int(self.x)
            cuty = int(self.y)
            img = self.img[cuty:cuty + cuth, cutx:cutx + cutw]
            # now get the size of the image that was actually cut (some areas may be out of range)
            self.cuth, self.cutw = img.shape[:2]

            # highlight the pixel under the cursor, but only if the cut canvas area is
            # small enough that there's any point (it's a slow operation!)
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

            # now resize the cut area up to fit the widget. Using area interpolation here:
            # cubic produced odd artifacts on float images
            img = cv.resize(img, dsize=(int(self.cutw / scale), int(self.cuth / scale)), interpolation=cv.INTER_AREA)
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

    def keyPressEvent(self, e):
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
            self.x = max(0, min(self.x, self.img.shape[1] - self.cutw))
            self.y = max(0, min(self.y, self.img.shape[0] - self.cuth))
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
        self.cursorX, self.cursorY = self.getImgCoords(e.pos())
        self.update()


def makesidebarLabel(t):
    lab = QtWidgets.QLabel(t)
    # lab.setMaximumHeight(15)
    lab.setMinimumWidth(100)
    return lab


## the containing widget, holding scroll bars and InnerCanvas widget

class Canvas(QtWidgets.QWidget):
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

    ## constructor
    def __init__(self, parent):
        super().__init__(parent)
        self.paintHook = None
        self.mouseHook = None
        self.keyHook = None
        self.graph = None
        self.nodeToUIChange = None
        self.ROInode = None
        self.recursing = False  # An ugly hack to avoid recursion in ROI nodes

        # outer layout is a horizontal box - the sidebar and canvas+scrollbars are in this
        outerlayout = QtWidgets.QHBoxLayout()
        self.setLayout(outerlayout)

        # the sidebar is a vbox, with labels (red,green,blue)
        # and channel name comboboxes below each.
        # Some of these are hideable and so go into a subwidget.

        self.sidebarwidget = QtWidgets.QWidget()
        sidebar = QtWidgets.QVBoxLayout()
        self.sidebarwidget.setLayout(sidebar)
        self.sidebarwidget.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                         QtWidgets.QSizePolicy.MinimumExpanding)

        outerlayout.addWidget(self.sidebarwidget)
        outerlayout.setAlignment(Qt.AlignTop)

        self.hideablebuttons = QtWidgets.QWidget()
        hideable = QtWidgets.QVBoxLayout()
        self.hideablebuttons.setLayout(hideable)
        sidebar.addWidget(self.hideablebuttons)

        # these are the actual widgets specifying which channel in the cube is viewed.
        # We need to deal with these carefully.
        hideable.addWidget(makesidebarLabel("RED source"))
        self.redChanCombo = QtWidgets.QComboBox()
        self.redChanCombo.currentIndexChanged.connect(self.redIndexChanged)
        hideable.addWidget(self.redChanCombo)
        hideable.addWidget(makesidebarLabel("GREEN source"))
        self.greenChanCombo = QtWidgets.QComboBox()
        self.greenChanCombo.currentIndexChanged.connect(self.greenIndexChanged)
        hideable.addWidget(self.greenChanCombo)
        hideable.addWidget(makesidebarLabel("BLUE source"))
        self.blueChanCombo = QtWidgets.QComboBox()
        self.blueChanCombo.currentIndexChanged.connect(self.blueIndexChanged)
        hideable.addWidget(self.blueChanCombo)

        # self.roiToggle = TextToggleButton("ROIs", "ROIs")
        self.roiToggle = QCheckBox("Show ROIs")
        hideable.addWidget(self.roiToggle)
        self.roiToggle.toggled.connect(self.roiToggleChanged)

        # self.spectrumToggle = TextToggleButton("Spectrum", "Spectrum")
        self.spectrumToggle = QCheckBox("Show spectrum")
        hideable.addWidget(self.spectrumToggle)
        self.spectrumToggle.toggled.connect(self.spectrumToggleChanged)

        self.saveButton = QtWidgets.QPushButton("Save RGB")
        hideable.addWidget(self.saveButton)
        self.saveButton.clicked.connect(self.saveButtonClicked)

        self.coordsText = QtWidgets.QLabel('')
        sidebar.addWidget(self.coordsText)

        self.roiText = QtWidgets.QLabel('')
        sidebar.addWidget(self.roiText)

        self.dimensions = QtWidgets.QLabel('')
        sidebar.addWidget(self.dimensions)

        ## widgets done; add stretch at the end so that the above widgets don't expand.
        sidebar.addStretch(10)

        sidebar.setContentsMargins(0, 0, 0, 0)

        splitter = QtWidgets.QSplitter()
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

        self.spectrumWidget = SpecPlot()
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
        layout.addWidget(self.resetButton, 1, 1)
        self.resetButton.clicked.connect(self.reset)

        # the mapping we are using - the image owns this, we just get a ref. when
        # the tab is created
        self.mapping = None
        # previous image (in case mapping changes and we need to redisplay the old image with a new mapping)
        self.previmg = None
        self.isPremapped = False
        # entity to persist data in; should serialise and deserialise canvas settings
        self.persister = None
        self.roiToggle.setEnabled(False)  # because persister is None at first.

    def mouseMove(self, x, y, event):
        self.coordsText.setText(f"{x},{y}")
        self.showSpectrum()
        if self.mouseHook is not None:
            self.mouseHook.canvasMouseMoveEvent(x, y, event)

    ## call this if this is only ever going to display single channel images
    # or annotated RGB images (obviating the need for source drop-downs)
    def hideMapping(self):
        self.hideablebuttons.setVisible(False)

    ## this works by setting a data structure which is persisted, and holds some of our
    # data rather than us. Ugly, yes.
    def setPersister(self, p):
        self.persister = p
        self.roiToggle.setEnabled(True)
        self.roiToggle.setChecked(p.showROIs)

    ## if this is a canvas for an ROI node, set that node.
    def setROINode(self, n):
        self.ROInode = n

    ## some canvas persistence data is to be stored from an object into a dict.
    # Get the data from the object and store it in the dict.
    @staticmethod
    def serialise(o, data):
        data['showROIs'] = o.showROIs

    ## inverse of setPersistData, done when we deserialise something
    @staticmethod
    def deserialise(o, data):
        o.showROIs = data.get('showROIs', False)

    ## prepare an object for holding some of our data
    @staticmethod
    def initPersistData(o):
        if not hasattr(o, 'showROIs'):
            o.showROIs = False

    # these sets a reference to the mapping this canvas is using - bear in mind this class can mutate
    # that mapping!
    def setMapping(self, mapping):
        self.mapping = mapping

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
        self.persister.showROIs = v
        self.redisplay()

    def spectrumToggleChanged(self, v):
        self.spectrumWidget.setHidden(not v)

    def saveButtonClicked(self, c):
        if self.previmg is None:
            return
        img = self.previmg.rgb()
        # convert to 8-bit integer from 32-bit float
        img8 = (img * 255).astype('uint8')
        # and change endianness
        img8 = cv.cvtColor(img8, cv.COLOR_RGB2BGR)
        res = QtWidgets.QFileDialog.getSaveFileName(self, 'Save RGB image as PNG',
                                                    os.path.expanduser(pcot.config.getDefaultDir('savedimages')),
                                                    "PNG images (*.png)")
        if res[0] != '':
            path = res[0]
            # make sure it ends with PNG!
            (root, ext) = os.path.splitext(path)
            if ext != '.png':
                ext += '.png'
            path = root + ext
            pcot.config.setDefaultDir('images', os.path.dirname(os.path.realpath(path)))
            cv.imwrite(path, img8)
            ui.log("Image written to " + path)

        pass

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
        # cache the image in case the mapping changes
        self.previmg = img
        # When we're using a "premapped" image, whenever we redisplay, we'll have to recalculate the node:
        # when we change the mapping (which is why we would redisplay) it's the node code which regenerates
        # the remapped image.
        self.nodeToUIChange = nodeToUIChange
        # This will clear the screen if img is None
        self.redisplay()

    def redisplay(self):
        # Note that we are doing ugly things to avoid recursion here. In some of the ROI nodes, this can happen:
        # updatetabs -> onNodeChanged -> display -> redisplay -> updatetabs...
        # This is the simplest way to avoid it.
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
        elif self.persister.showROIs:
            # if we're displaying all ROIs, show that pixel count (and ROI count)
            txt = "{} pixels\nin {} ROIs".format(sum([x.pixels() for x in self.previmg.rois]),
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

        self.canvas.display(self.previmg, self.isPremapped, showROIs=self.persister.showROIs)
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
            self.spectrumWidget.setData("No image in canvas")
            return
        if self.previmg.channels < 2:
            if 0 <= x < self.previmg.w and 0 <= y < self.previmg.h:
                self.spectrumWidget.setData(f"Single channel - intensity {self.previmg.img[y,x]}")
            return

        # within the coords, and multichannel image present

        if 0 <= x < self.previmg.w and 0 <= y < self.previmg.h and self.previmg.channels > 1:
            img = self.previmg
            dat = img.img[y, x, :]  # get the pixel data

            # get the channels which have a single wavelength
            # what do we do if they don't? I don't think you can display a spectrum!

            wavelengths = [img.wavelength(x) for x in range(img.channels)]

            goodWavelengths = [x for x in wavelengths if x > 0]
            chans = [x for x in range(img.channels) if wavelengths[x] > 0]

            # and get the data from the pixel which si for those wavelengths
            dat = [dat[x] for x in chans]

            # now plot x=wavelengths,y=dat
            self.spectrumWidget.setData(zip(goodWavelengths, dat))
