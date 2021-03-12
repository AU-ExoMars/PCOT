import pancamimage

from xform import xformtype, XFormType
from xforms.tabimage import TabImage


@xformtype
class XformCalib(XFormType):
    """mock calibration: takes ellipse data (or more realistically calibration data
    generated from ellipses) and calibrates the image accordingly"""

    def __init__(self):
        super().__init__("calib", "calibration", "0.0.0")
        self.addInputConnector("img", "img")
        self.addInputConnector("data", "ellipse")
        self.addOutputConnector("out", "img")

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None
        node.data = None

    def perform(self, node):
        node.img = node.getInput(0)
        node.setOutput(0, node.img)
