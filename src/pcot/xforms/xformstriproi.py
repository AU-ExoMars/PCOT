import pcot.conntypes as conntypes
from pcot.xform import xformtype, XFormType, Datum
from pcot.xforms.tabimage import TabImage


@xformtype
class XformStripROI(XFormType):
    """Strip ROIs from an image"""

    def __init__(self):
        super().__init__("striproi", "regions", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("", conntypes.IMG)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is not None:
            img = img.copy()
            img.rois = []
        node.img = img
        node.setOutput(0, Datum(conntypes.IMG, img))
