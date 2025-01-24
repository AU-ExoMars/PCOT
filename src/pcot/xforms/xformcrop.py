from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabdata import TabData


@xformtype
class XformCropROI(XFormType):
    """
    Crops an image to a rectangle which is the union of its regions of interest.
    """

    def __init__(self):
        super().__init__("croproi", "ROI edit", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.params = TaggedDictType()  # no parameters

    def createTab(self, n, w):
        return TabData(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            # create a new image, set it to use this node's mapping
            img = img.cropROI()
            # tell it to use the node's mapping so that the canvas
            # will work correctly
            img.mapping = node.mapping
            # and strip the ROIs
            img.rois = []
            out = Datum(Datum.IMG, img)
        else:
            out = None
        node.setOutput(0, out)
