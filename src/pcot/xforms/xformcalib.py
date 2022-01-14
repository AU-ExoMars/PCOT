from pcot.datum import Datum

from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


@xformtype
class XformCalib(XFormType):
    """
    calibration: takes ellipse data (or more realistically calibration data
    generated from ellipses) and calibrates the image accordingly. Not yet implemented"""

    def __init__(self):
        super().__init__("calib", "calibration", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addInputConnector("data", Datum.ELLIPSE)
        self.addOutputConnector("out", Datum.IMG)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None
        node.data = None

    def perform(self, node):
        node.img = node.getInput(0, Datum.IMG)
        node.setOutput(0, Datum(Datum.IMG, node.img))
