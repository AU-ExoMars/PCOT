from pcot import conntypes
from pcot.ui.tabs import Tab
from pcot.xform import XFormType, xformtype

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


@xformtype
class XFormStitch(XFormType):
    """This node performs manual stitching of multiple images into a single image."""

    def __init__(self):
        super().__init__("stitch", "processing", "0.0.0")
        for i in range(8):
            self.addInputConnector(str(i), conntypes.IMG, desc="Input image {}".format(i))
        self.addOutputConnector("", conntypes.IMG, desc="Output image")
        self.hasEnable = True
        # self.autoserialise = ('mode',)

    def createTab(self, n, w):
        return TabStitch(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        node.img = None
        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))


class TabStitch(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabstitch.ui')
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
