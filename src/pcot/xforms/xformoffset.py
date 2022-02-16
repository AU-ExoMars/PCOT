import numpy as np

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.xform import xformtype, XFormType


@xformtype
class XFormOffset(XFormType):
    """
    offset an image. Will create a zero band on one edge and clip on the opposite.
    ROIs are not honoured, but are passed through."""

    def __init__(self):
        super().__init__("offset", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('x', 'y')
        self.hasEnable = True

    def createTab(self, n, w):
        return TabOffset(n, w)

    def init(self, node):
        node.img = None
        node.x = 0
        node.y = 0

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            out = None
        elif not node.enabled:
            out = img
        else:
            # make new image the size of the old one
            newimg = np.zeros(img.img.shape, dtype=np.float32)
            xs = -min(node.x, 0)  # offset into source image
            ys = -min(node.y, 0)  # offset into source image
            xd = max(node.x, 0)  # offset into dest
            yd = max(node.y, 0)  # offset into dest
            # size of region to copy
            w = img.w - max(abs(xd), abs(xs))
            h = img.h - max(abs(yd), abs(ys))

            s = img.img[ys:ys + h, xs:xs + w]
            newimg[yd:yd + h, xd:xd + w] = s
            # remember to copy ROI            
            out = ImageCube(newimg, node.mapping, img.sources)

        node.img = Datum(Datum.IMG, out)
        node.setOutput(0, node.img)


class TabOffset(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'taboffset.ui')
        self.w.xoff.editingFinished.connect(self.xChanged)
        self.w.yoff.editingFinished.connect(self.yChanged)

        self.nodeChanged()

    def xChanged(self):
        self.mark()
        self.node.x = int(self.w.xoff.text())
        self.changed()

    def yChanged(self):
        self.mark()
        self.node.y = int(self.w.yoff.text())
        self.changed()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.xoff.setText(str(self.node.x))
        self.w.yoff.setText(str(self.node.y))
        self.w.canvas.display(self.node.img)
