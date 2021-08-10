import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import Qt

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
        # node.order = [i for i in range(NUMINPUTS)]
        node.order = [0, 3, 1, 2, 4, 7, 6, 5]

    def perform(self, node):
        # get a list of actual active inputs, rearranged for ordering
        images = [node.getInput(node.order[i], conntypes.IMG) for i in range(NUMINPUTS)]
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


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return ["fix", "blorp"][section]
        return super().headerData(section, orientation, role)


class TabStitch(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabstitch.ui')
        self.model = TableModel([
            ["foo", 1],
            ["bar", 3],
            ["baz", 2],
            ["qux", 4]
        ])
        self.w.table.setModel(self.model)
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.display(self.node.img)
