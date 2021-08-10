import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QItemSelection, QItemSelectionModel
import cv2 as cv

from pcot import conntypes
from pcot.pancamimage import ImageCube
from pcot.ui.tabs import Tab
from pcot.xform import XFormType, xformtype, XFormException

"""
Notes during dev.

Each input image requires 2 parameters - offset and ordering. We need some kind of list on the right showing
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
            self.addInputConnector(str(i), conntypes.IMG, desc="Input image {}".format(i))
        self.addOutputConnector("", conntypes.IMG, desc="Output image")
        self.hasEnable = True
        self.autoserialise = ('offsets', 'order')

    def createTab(self, n, w):
        return TabStitch(n, w)

    def init(self, node):
        # these are the image offsets
        node.offsets = [(i * 50, i * 50 - 200) for i in range(NUMINPUTS)]
        # and the default ordering
        node.order = [i for i in range(NUMINPUTS)]
        node.present = [False for _ in range(NUMINPUTS)]
        node.selected = []
        node.rgbImage = None
        node.img = None

    def perform(self, node):
        realIns = [node.getInput(i, conntypes.IMG) for i in range(NUMINPUTS)]
        # get a list of actual active inputs, rearranged for ordering

        images = [realIns[node.order[i]] for i in range(NUMINPUTS)]
        node.present = [i is not None for i in images]  # keep an array of booleans indicating if an item is present

        # same with offsets
        offsets = [node.offsets[node.order[i]] for i in range(NUMINPUTS) if images[i] is not None]
        images = [i for i in images if i is not None]  # done separately to avoid double getInput call.
        if len(images) == 0:
            node.img = None
            node.setOutput(0, None)
            return

        if len(set([i.channels for i in images])) > 1:
            raise XFormException('DATA', 'all images must have the same number of channels for stitching')

        # work out the bounding box
        minx = min([p[0] for p in offsets])
        miny = min([p[1] for p in offsets])
        maxx = max([p[0] + img.w for p, img in zip(offsets, images)])
        maxy = max([p[1] + img.h for p, img in zip(offsets, images)])

        # create an image of that size to compose the images into
        chans = images[0].channels
        img = np.zeros((maxy - miny, maxx - minx, chans), dtype=np.float32)

        # compose the sources - this is a channel-wise union of all the sources
        # in all the images.
        sources = [set() for i in range(chans)]  # one empty set for each channel
        for srcimg in images:
            for c in range(chans):
                sources[c] = sources[c].union(srcimg.sources[c])

        # perform the composition
        for offset, srcimg in zip(offsets, images):
            # calculate the actual image offset
            x = offset[0] - minx
            y = offset[1] - miny
            # paste in
            img[y:y + srcimg.h, x:x + srcimg.w] = srcimg.img

        # generate the output
        node.img = ImageCube(img, node.mapping, sources)

        node.rgbImage = node.img.rgbImage()
        # note that we are now not reordering so that the selection makes sense.
        for i, (inp, off) in enumerate(zip(realIns, node.offsets)):
            if inp is not None and i in node.selected:
                x = off[0]-minx
                y = off[1]-miny
                cv.rectangle(node.rgbImage.img, (x, y), (x+inp.w, y+inp.h), (1, 0, 0), 10)

    def uichange(self, node):
        self.perform(node)


COLNAMES = ["index", "offset X", "offset Y"]


class TableModel(QtCore.QAbstractTableModel):
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
        self.model = TableModel(node)
        self.w.table.setModel(self.model)
        self.w.table.setColumnWidth(0, 10)
        self.w.table.setColumnWidth(1, 70)
        self.w.table.setColumnWidth(2, 70)
        self.w.up.pressed.connect(self.upPressed)
        self.w.down.pressed.connect(self.downPressed)
        self.w.table.selectionModel().selectionChanged.connect(self.selChanged)
        self.nodeChanged()

    def selChanged(self, sel, desel):
        self.node.selected = self.getSelected()
        self.node.uichange()
        self.w.canvas.redisplay()

    def selectRow(self, r):
        sel = QItemSelection(self.model.index(r, 0), self.model.index(r, 2))
        self.w.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)

    def getSelected(self):
        return [mi.row() for mi in self.w.table.selectionModel().selectedRows()]

    def upPressed(self):
        o = self.node.order
        for r in self.getSelected():
            if r > 0:
                o[r - 1], o[r] = o[r], o[r - 1]
            self.selectRow(r-1)
        self.changed()

    def downPressed(self):
        o = self.node.order
        for r in self.getSelected():
            if r < NUMINPUTS-1:
                o[r + 1], o[r] = o[r], o[r + 1]
            self.selectRow(r+1)
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        if self.node.img is not None:  # premapped rgb
            self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
        self.w.table.viewport().update()  # force table redraw
