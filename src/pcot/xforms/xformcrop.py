from pcot.datum import Datum
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabdata import TabData


@xformtype
class XformCropROI(XFormType):
    """
    Crops an image to a rectangle which is the union of its regions of interest"""

    def __init__(self):
        super().__init__("croproi", "ROI edit", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        return TabData(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            # create a new image, set it to use this node's mapping
            img = img.cropROI()
            img.mapping = node.mapping

        node.out = Datum(Datum.IMG, img)
        node.setOutput(0, node.out)
