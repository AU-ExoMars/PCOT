from pcot.datum import Datum
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


@xformtype
class XformCropROI(XFormType):
    """
    Crops an image to a rectangle which is the union of its regions of interest"""

    def __init__(self):
        super().__init__("croproi", "ROI edit", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            img = img.cropROI()
        node.out = Datum(Datum.IMG, img)
        node.setOutput(0, node.out)
