import logging

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import Qt, QItemSelection, QItemSelectionModel
import cv2 as cv
from PySide2.QtGui import QKeyEvent

from pcot import dq
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, taggedPointListType
from pcot.sources import MultiBandSource, nullSource
from pcot.ui.tabs import Tab
from pcot.xform import XFormType, xformtype, XFormException

logger = logging.getLogger(__name__)

"""
Notes during dev.

Each input image requires 2 parameters - offset and ordering. There is a list on the right showing
the input images for reference, so we can see what's coming in and perhaps easily select. With an image selected,
we need to be able to 
1) move it by dragging in the image
2) move it by arrow keys (possible with shift and ctrl for different "speeds")
3) move it up and down in the order (pgup/pgdn?)

Composing the image is a matter of finding the bounding box and creating an image of that size,
then finding the coordinates of the top left of each image within that bounding box and slapping them in.
Coordinates of each image are stored (before this stage) as simple offsets from a notional origin, so they
all start at (0,0).
"""

NUMINPUTS = 8


@xformtype
class XFormStitch(XFormType):
    """This node performs manual stitching of multiple images into a single image."""

    def __init__(self):
        super().__init__("stitch", "processing", "0.0.0")
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), Datum.IMG, desc="Input image {}".format(i))
        self.addOutputConnector("", Datum.IMG, desc="Output image")

        self.params = TaggedDictType(
            order=("Order of images", TaggedListType(int, list(range(NUMINPUTS)), 0)),
            showImage=("Show image", bool, True),
            offsets=("Offsets of images", taggedPointListType, None))

    def serialise(self, node):
        """Do CTAS (Complex Tagged Aggregate Serialisation) on the node into the existing parameters field"""
        node.params.offsets.clear()  # remove old offsets from the tagged list
        # add the actual offsets to the tagged list
        for i in range(NUMINPUTS):
            p = node.params.offsets.append_default()
            p.x, p.y = node.offsets[i]

        node.params.order.clear()
        for v in node.order:
            node.params.order.append(v)


    def nodeDataFromParams(self, node):
        """CTAS from the tagged aggregate back into the node"""
        # convert order to plain list in node
        node.order = node.params.order.get()
        # convert offsets to list of x,y tuples in node
        node.offsets = []
        for p in node.params.offsets:
            node.offsets.append((p.x, p.y))

    def createTab(self, n, w):
        return TabStitch(n, w)

    def init(self, node):
        # these are the image offsets we really use.
        node.offsets = [(i * 50, i * 50 - 200) for i in range(NUMINPUTS)]
        # and the default ordering - this maps from run order to input number
        node.order = [i for i in range(NUMINPUTS)]
        # list of selected items, indexed by run order (so equals selected rows in the table)
        node.selected = []
        # map of inputs which are connected
        node.present = [False for _ in range(NUMINPUTS)]
        # RGB image used on canvas
        node.canvimage = None
        node.showImage = True

    def perform(self, node):
        inputs = [node.getInput(i, Datum.IMG) for i in range(NUMINPUTS)]

        # filter out inputs which aren't connected, for BB calculations
        activeInputImages = [i for i in inputs if i is not None]
        node.present = [i is not None for i in inputs]
        # get the offsets of those inputs, for the same purpose
        activeInputOffsets = [node.offsets[i] for i in range(NUMINPUTS) if inputs[i] is not None]
        # exit early if no active inputs
        if len(activeInputImages) == 0:
            node.img = None
            node.setOutput(0, Datum(Datum.IMG, None, nullSource))
            return
        # throw an error if the images don't all have the same channel count
        if len(set([i.channels for i in activeInputImages])) > 1:
            raise XFormException('DATA', 'all images must have the same number of channels for stitching')

        # work out the bounding box
        minx = min([p[0] for p in activeInputOffsets])
        miny = min([p[1] for p in activeInputOffsets])
        maxx = max([p[0] + img.w for p, img in zip(activeInputOffsets, activeInputImages)])
        maxy = max([p[1] + img.h for p, img in zip(activeInputOffsets, activeInputImages)])

        # create an image of that size to compose the images into. We have to deal with the fact that
        # 1-band images are (h,w) while multiband images are (h,w,n).
        chans = activeInputImages[0].channels
        if chans == 1:
            img = np.zeros((maxy - miny, maxx - minx), dtype=np.float32)
            unc = np.zeros((maxy - miny, maxx - minx), dtype=np.float32)
            dqs = np.full((maxy - miny, maxx - minx), dq.NODATA | dq.NOUNCERTAINTY, dtype=np.uint16)
        else:
            img = np.zeros((maxy - miny, maxx - minx, chans), dtype=np.float32)
            unc = np.zeros((maxy - miny, maxx - minx, chans), dtype=np.float32)
            dqs = np.full((maxy - miny, maxx - minx, chans), dq.NODATA | dq.NOUNCERTAINTY, dtype=np.uint16)

        # compose the sources - this is a channel-wise union of all the sources
        # in all the images.
        sources = MultiBandSource.createBandwiseUnion([x.sources for x in activeInputImages])

        # perform the composition - this time we're just stepping through the inputs, connected or not
        # as it's easier to avoid errors.
        for drawOrder in range(NUMINPUTS):
            # work out which image to display from the ordering
            i = node.order[drawOrder]
            if inputs[i] is not None:
                # calculate the actual image offset
                x = node.offsets[i][0] - minx
                y = node.offsets[i][1] - miny
                # paste in
                srcimg = inputs[i]
                try:
                    img[y:y + srcimg.h, x:x + srcimg.w] = srcimg.img
                    unc[y:y + srcimg.h, x:x + srcimg.w] = srcimg.uncertainty
                    dqs[y:y + srcimg.h, x:x + srcimg.w] = srcimg.dq
                except ValueError as e:
                    logger.error(
                        "stored offset:{},{} min:{},{} xy:{},{}".format(node.offsets[i][0], node.offsets[i][1], minx,
                                                                        miny, x, y))
                    logger.error(img.shape)
                    logger.error(srcimg.img.shape)
                    logger.error(y, y + srcimg.h, x, x + srcimg.w)
                    raise e

        # generate the output
        outimg = ImageCube(img, node.mapping, sources, uncertainty=unc, dq=dqs)
        node.setOutput(0, Datum(Datum.IMG, outimg))

        # now draw the selected inputs
        node.canvimage = outimg.rgbImage()

        if node.showImage:
            for i in range(NUMINPUTS):
                inp = inputs[node.order[i]]
                if inp is not None and i in node.selected:
                    off = node.offsets[node.order[i]]
                    x = off[0] - minx
                    y = off[1] - miny
                    cv.rectangle(node.canvimage.img, (x, y), (x + inp.w, y + inp.h), (1, 0, 0), 10)

    def uichange(self, node):
        node.timesPerformed += 1
        self.perform(node)

    def clearData(self, xform):
        xform.canvimage = None


COLNAMES = ["index", "offset X", "offset Y"]


# TODO use the new TableModel??
class StitchTableModel(QtCore.QAbstractTableModel):
    def __init__(self, node):
        super().__init__()
        self.node = node

    def data(self, index, role):
        n = self.node
        if role == Qt.DisplayRole:
            r = index.row()
            c = index.column()
            i = n.order[r]
            offset = n.offsets[i]
            present = n.present[i]

            if c == 0:
                return i
            elif c == 1:
                return offset[0] if present else ""
            elif c == 2:
                return offset[1] if present else ""
            else:
                return "???"

    def rowCount(self, index):
        return NUMINPUTS

    def columnCount(self, index):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLNAMES[section]
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(section)
        return super().headerData(section, orientation, role)

    def submit(self):
        return True


class TabStitch(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabstitch.ui')
        self.model = StitchTableModel(node)
        self.w.canvas.keyHook = self
        self.w.table.setModel(self.model)
        self.w.table.setColumnWidth(0, 30)
        self.w.table.setColumnWidth(1, 70)
        self.w.table.setColumnWidth(2, 70)
        self.w.up.pressed.connect(self.upPressed)
        self.w.down.pressed.connect(self.downPressed)
        self.w.table.selectionModel().selectionChanged.connect(self.selChanged)
        self.w.showimage.toggled.connect(self.showImageToggled)
        self.nodeChanged()

    def showImageToggled(self):
        self.node.showImage = self.w.showimage.isChecked()
        self.changed(uiOnly=True)

    def selChanged(self, sel, desel):
        self.node.selected = self.getSelected()
        self.changed(uiOnly=True)

    def selectRow(self, r):
        sel = QItemSelection(self.model.index(r, 0), self.model.index(r, 2))
        self.w.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)

    def getSelected(self):
        return [mi.row() for mi in self.w.table.selectionModel().selectedRows()]

    def upPressed(self):
        self.mark()
        o = self.node.order
        for r in self.getSelected():
            if r > 0:
                o[r - 1], o[r] = o[r], o[r - 1]
            self.selectRow(r - 1)
        self.changed()

    def downPressed(self):
        self.mark()
        o = self.node.order
        for r in self.getSelected():
            if r < NUMINPUTS - 1:
                o[r + 1], o[r] = o[r], o[r + 1]
            self.selectRow(r + 1)
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.showimage.setChecked(self.node.showImage)
        img = self.node.getOutput(0, Datum.IMG)
        if img is not None:  # draw the premapped rgb, not the actual stitched image
            self.w.canvas.display(self.node.canvimage, img, self.node)
        self.w.table.viewport().update()  # force table redraw

    def moveSel(self, e: QKeyEvent, x, y):
        self.mark()
        scale = 10
        if e.modifiers() & Qt.ControlModifier:
            scale *= 10
        if e.modifiers() & Qt.ShiftModifier:
            scale /= 10

        n = self.node
        for r in self.getSelected():
            xx, yy = n.offsets[r]
            xx += scale * x
            yy += scale * y
            n.offsets[r] = int(xx), int(yy)
        if len(self.getSelected()):
            self.changed()

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_Left:
            self.moveSel(e, -1, 0)
        elif k == Qt.Key_Right:
            self.moveSel(e, 1, 0)
        elif k == Qt.Key_Up:
            self.moveSel(e, 0, -1)
        elif k == Qt.Key_Down:
            self.moveSel(e, 0, 1)
