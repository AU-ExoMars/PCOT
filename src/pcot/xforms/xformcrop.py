import pcot.conntypes as conntypes
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


@xformtype
class XformCropROI(XFormType):
    """Crops an image to a rectangle which is the union of its regions of interest"""

    def __init__(self):
        super().__init__("croproi", "regions", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("", conntypes.IMG)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is not None:
            img = img.cropROI()
        node.img = img
        node.setOutput(0, conntypes.Datum(conntypes.IMG, img))
