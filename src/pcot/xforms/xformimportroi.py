import pcot.conntypes as conntypes
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


@xformtype
class XformImportROI(XFormType):
    """Import a ROI into an image which was originally set on another image"""

    def __init__(self):
        super().__init__("importroi", "regions", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addInputConnector("roi", conntypes.ROI)
        self.addOutputConnector("", conntypes.IMG)

    def createTab(self, n, w):
        t = TabImage(n, w)
        # modify the canvas to show own-ROI data
        t.w.canvas.setROINode(n)
        return t

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        roi = None
        if img is not None:
            roi = node.getInput(1, conntypes.ROI)
            if roi is not None:
                img = img.copy()
                img.rois.append(roi)
        node.img = img
        node.roi = roi
        node.setOutput(0, conntypes.Datum(conntypes.IMG, img))
