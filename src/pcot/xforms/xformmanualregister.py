import cv2 as cv
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QMessageBox

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot.channelsource import REDINTERNALSOURCE, GREENINTERNALSOURCE, \
    BLUEINTERNALSOURCE
from pcot.pancamimage import ImageCube
from pcot.utils import text
from pcot.xform import XFormType, xformtype

VIEWMODE_BOTH = 0
VIEWMODE_FIXED = 1
VIEWMODE_MOVING = 2

EDITMODE_SOURCE = 0
EDITMODE_DEST = 1


# channel-agnostic RGB of an image
def prep(img: ImageCube) -> np.array:
    mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
    canvimg = cv.transform(img.img, mat)
    mn = np.min(canvimg)
    mx = np.max(canvimg)
    return (canvimg - mn) / (mx - mn)


def drawpoints(img, lst, selidx, col, iscurmode):
    i = 0
    fontline = 3 if iscurmode else 2
    fontsize = 10

    for p in lst:
        cv.circle(img, p, 7, col, fontline)
        x, y = p
        text.write(img, str(i), x + 10, y + 10, False, fontsize, fontline, col)
        i = i + 1

    if selidx is not None:
        cv.circle(img, lst[selidx], 10, col, fontline+2)


@xformtype
class XFormManualRegister(XFormType):

    def __init__(self):
        super().__init__("manual register", "processing", "0.0.0")
        self.addInputConnector("moving", conntypes.IMG)
        self.addInputConnector("fixed", conntypes.IMG)
        self.addOutputConnector("moved", conntypes.IMG)

    def init(self, node):
        node.img = None
        node.viewmode = VIEWMODE_BOTH
        node.editmode = EDITMODE_SOURCE
        node.hideother = False

        # source and destination points - there is a 1:1 mapping between the two
        node.src = []  # ditto
        node.dest = []  # list of (x,y) points
        # index of selected points in each list (or None)
        node.destSel = None
        node.srcSel = None

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
                img = (prep(movingImg) + prep(fixedImg)) / 2

            # create a new image for the canvas; we'll draw on it.
            canvimg = cv.merge([img, img, img])

            # now draw the points

            if not node.hideother or node.editmode == EDITMODE_SOURCE:
                drawpoints(canvimg, node.src, node.srcSel, (1, 1, 0), node.editmode == EDITMODE_SOURCE)
            if not node.hideother or node.editmode == EDITMODE_DEST:
                drawpoints(canvimg, node.dest, node.destSel, (0, 1, 1), node.editmode == EDITMODE_DEST)

            # grey, but 3 channels so I can draw on it!
            node.canvimg = ImageCube(canvimg, node.mapping,
                                     [{REDINTERNALSOURCE}, {GREENINTERNALSOURCE}, {BLUEINTERNALSOURCE}])

            node.img = movingImg  # this is the one we need to warp!

        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))

    @staticmethod
    def delSelPoint(n):
        if n.editmode == EDITMODE_DEST and n.destSel is not None:
            del n.dest[n.destSel]
            n.destSel = None
        elif n.editmode == EDITMODE_SOURCE and n.srcSel is not None:
            del n.src[n.srcSel]
            n.srcSel = None

    @staticmethod
    def moveSelPoint(n, x, y):
        if n.editmode == EDITMODE_DEST:
            if n.destSel is not None:
                n.dest[n.destSel] = (x, y)
                return True
        elif n.editmode == EDITMODE_SOURCE:
            if n.srcSel is not None:
                n.src[n.srcSel] = (x, y)
                return True
        return False

    @staticmethod
    def addPoint(n, x, y):
        lst = n.dest if n.editmode == EDITMODE_DEST else n.src
        lst.append((x, y))

    @staticmethod
    def selPoint(n, x, y):
        lst = n.dest if n.editmode == EDITMODE_DEST else n.src
        pt = None
        mindist = None
        for idx in range(len(lst)):
            px, py = lst[idx]
            dx = px - x
            dy = py - y
            dsq = dx * dx + dy * dy
            if dsq < 100 and (mindist is None or dsq < mindist):
                pt = idx
                mindist = dsq
        if pt is not None:
            if n.editmode == EDITMODE_DEST:
                n.destSel = pt
            else:
                n.srcSel = pt

    def createTab(self, n, w):
        return TabManualReg(n, w)


class TabManualReg(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabmanreg.ui')
        self.mouseDown = False
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setPersister(node)
        self.w.canvas.keyHook = self
        self.w.canvas.mouseHook = self

        self.w.radioBoth.toggled.connect(self.radioViewToggled)
        self.w.radioFixed.toggled.connect(self.radioViewToggled)
        self.w.radioMoving.toggled.connect(self.radioViewToggled)

        self.w.radioDest.toggled.connect(self.radioEditToggled)
        self.w.radioSource.toggled.connect(self.radioEditToggled)

        self.w.hideOther.toggled.connect(self.hideOtherToggled)

        self.w.applyButton.clicked.connect(self.applyClicked)
        self.w.clearButton.clicked.connect(self.clearClicked)

        self.onNodeChanged()

    def applyClicked(self):
        pass

    def clearClicked(self):
        if QMessageBox.question(self.parent(), "Clear all points", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            pass

    def hideOtherToggled(self):
        self.node.hideother = self.w.hideOther.isChecked()
        self.changed()

    def radioViewToggled(self):
        if self.w.radioBoth.isChecked():
            self.node.viewmode = VIEWMODE_BOTH
        elif self.w.radioFixed.isChecked():
            self.node.viewmode = VIEWMODE_FIXED
        elif self.w.radioMoving.isChecked():
            self.node.viewmode = VIEWMODE_MOVING
        self.changed()

    def radioEditToggled(self):
        if self.w.radioDest.isChecked():
            self.node.editmode = EDITMODE_DEST
        elif self.w.radioSource.isChecked():
            self.node.editmode = EDITMODE_SOURCE
        self.changed()

    def onNodeChanged(self):
        self.w.radioBoth.setChecked(self.node.viewmode == VIEWMODE_BOTH)
        self.w.radioFixed.setChecked(self.node.viewmode == VIEWMODE_FIXED)
        self.w.radioMoving.setChecked(self.node.viewmode == VIEWMODE_MOVING)

        self.w.radioSource.setChecked(self.node.editmode == EDITMODE_SOURCE)
        self.w.radioDest.setChecked(self.node.editmode == EDITMODE_DEST)

        self.w.hideOther.setChecked(self.node.hideother)

        if self.node.img is not None:
            # displaying a premapped image
            self.w.canvas.display(self.node.canvimg, self.node.canvimg, self.node)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_1:
            self.node.viewmode = VIEWMODE_BOTH
            self.changed()
        elif k == Qt.Key_2:
            self.node.viewmode = VIEWMODE_MOVING
            self.changed()
        elif k == Qt.Key_3:
            self.node.viewmode = VIEWMODE_FIXED
            self.changed()
        elif k == Qt.Key_M:
            if self.node.editmode == EDITMODE_SOURCE:
                self.node.editmode = EDITMODE_DEST
            elif self.node.editmode == EDITMODE_DEST:
                self.node.editmode = EDITMODE_SOURCE
            self.changed()
        elif k == Qt.Key_H:
            self.node.hideother = not self.node.hideother
            self.changed()
        elif k == Qt.Key_Delete:
            self.node.type.delSelPoint(self.node)
            self.changed()

    def canvasMouseMoveEvent(self, x, y, e):
        if self.mouseDown:
            if self.node.type.moveSelPoint(self.node, x, y):
                self.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        if e.modifiers() & Qt.ShiftModifier:
            self.node.type.addPoint(self.node, x, y)
        else:
            self.node.type.selPoint(self.node, x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
