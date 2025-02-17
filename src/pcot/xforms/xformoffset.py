import numpy as np

from pcot import dq
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType
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
        self.params = TaggedDictType(
            x=("X offset", int, 0),
            y=("Y offset", int, 0)
        )

    def createTab(self, n, w):
        return TabOffset(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            out = None
        else:
            p = node.params
            # make new image, new unc and new DQ
            newimg = np.zeros(img.img.shape, dtype=np.float32)
            newunc = np.zeros(img.img.shape, dtype=np.float32)
            newdq = np.full(img.img.shape, dq.NOUNCERTAINTY | dq.NODATA, dtype=np.uint16)
            xs = -min(p.x, 0)  # offset into source image
            ys = -min(p.y, 0)  # offset into source image
            xd = max(p.x, 0)  # offset into dest
            yd = max(p.y, 0)  # offset into dest
            # size of region to copy
            w = img.w - max(abs(xd), abs(xs))
            h = img.h - max(abs(yd), abs(ys))

            newimg[yd:yd + h, xd:xd + w] = img.img[ys:ys + h, xs:xs + w]
            newunc[yd:yd + h, xd:xd + w] = img.uncertainty[ys:ys + h, xs:xs + w]
            newdq[yd:yd + h, xd:xd + w] = img.dq[ys:ys + h, xs:xs + w]
            # remember to copy ROI
            out = ImageCube(newimg, node.mapping, img.sources, dq=newdq, uncertainty=newunc)

        node.setOutput(0, Datum(Datum.IMG, out))


class TabOffset(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'taboffset.ui')
        self.w.xoff.editingFinished.connect(self.xChanged)
        self.w.yoff.editingFinished.connect(self.yChanged)

        self.nodeChanged()

    def xChanged(self):
        self.mark()
        self.node.params.x = int(self.w.xoff.text())
        self.changed()

    def yChanged(self):
        self.mark()
        self.node.params.y = int(self.w.yoff.text())
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.xoff.setText(str(self.node.params.x))
        self.w.yoff.setText(str(self.node.params.y))
        self.w.canvas.display(self.node.getOutput(0, Datum.IMG))
