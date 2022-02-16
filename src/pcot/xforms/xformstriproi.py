from pcot.datum import Datum
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


@xformtype
class XformStripROI(XFormType):
    """Strip ROIs from an image"""

    def __init__(self):
        super().__init__("striproi", "ROI edit", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        out = node.getInput(0, Datum.IMG)
        if out is not None:
            out = out.copy()
            out.rois = []
        node.out = Datum(Datum.IMG, out)
        node.setOutput(0, out)
