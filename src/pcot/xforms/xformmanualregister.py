import cv2 as cv
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot.channelsource import REDINTERNALSOURCE, GREENINTERNALSOURCE, \
    BLUEINTERNALSOURCE
from pcot.pancamimage import ImageCube
from pcot.xform import XFormType

VIEWMODE_BOTH = 0
VIEWMODE_FIXED = 1
VIEWMODE_MOVING = 2


# channel-agnostic RGB of an image
def prep(img: ImageCube) -> np.array:
    mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
    canvimg = cv.transform(img.img, mat)
    mn = np.min(canvimg)
    mx = np.max(canvimg)
    return (canvimg - mn) / (mx - mn)


#@xformtype
class XFormManualRegister(XFormType):

    def __init__(self):
        super().__init__("manual register", "processing", "0.0.0")
        self.addInputConnector("moving", conntypes.IMG)
        self.addInputConnector("fixed", conntypes.IMG)
        self.addOutputConnector("moved", conntypes.IMG)

    def init(self, node):
        node.img = None
        node.viewmode = VIEWMODE_BOTH

    def perform(self, node):
        # read images
        movingImg = node.getInput(0, conntypes.IMG)
        fixedImg = node.getInput(1, conntypes.IMG)

        if fixedImg is None or movingImg is None:
            node.img = None
        else:
            # this gets the appropriate image and also manipulates it.
            # Generally we convert RGB to grey; otherwise we'd have to store
            # quite a few mappings.
            if node.viewmode == VIEWMODE_FIXED:
                img = prep(movingImg)
            elif node.viewmode == VIEWMODE_MOVING:
                img = prep(fixedImg)
            else:
                img = (prep(movingImg)+prep(fixedImg))/2

            # create a new image for the canvas; we'll draw on it.

            # grey, but 3 channels so I can draw on it!
            node.canvimg = ImageCube(cv.merge([img, img, img]), node.mapping,
                                     [{REDINTERNALSOURCE}, {GREENINTERNALSOURCE}, {BLUEINTERNALSOURCE}])

            node.img = movingImg # this is the one we need to warp!

        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))

    def createTab(self, n, w):
        return TabManualReg(n, w)


class TabManualReg(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabmanreg.ui')
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setPersister(node)
        self.w.canvas.keyHook = self

        self.w.radioBoth.toggled.connect(self.radioToggled)
        self.w.radioFixed.toggled.connect(self.radioToggled)
        self.w.radioMoving.toggled.connect(self.radioToggled)

        self.onNodeChanged()

    def radioToggled(self):
        if self.w.radioBoth.isChecked():
            self.node.viewmode = VIEWMODE_BOTH
        elif self.w.radioFixed.isChecked():
            self.node.viewmode = VIEWMODE_FIXED
        elif self.w.radioMoving.isChecked():
            self.node.viewmode = VIEWMODE_MOVING
        self.changed()

    def onNodeChanged(self):
        self.w.radioBoth.setChecked(self.node.viewmode == VIEWMODE_BOTH)
        self.w.radioFixed.setChecked(self.node.viewmode == VIEWMODE_FIXED)
        self.w.radioMoving.setChecked(self.node.viewmode == VIEWMODE_MOVING)

        if self.node.img is not None:
            # displaying a premapped image
            self.w.canvas.display(self.node.canvimg, self.node.canvimg, self.node)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_1:
            self.node.viewmode = VIEWMODE_BOTH
            self.changed()
        elif e.key() == Qt.Key_2:
            self.node.viewmode = VIEWMODE_MOVING
            self.changed()
        elif e.key() == Qt.Key_3:
            self.node.viewmode = VIEWMODE_FIXED
            self.changed()
