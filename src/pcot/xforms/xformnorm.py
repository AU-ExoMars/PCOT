import pcot.conntypes as conntypes
import pcot.operations as operations
import pcot.ui.tabs
from pcot.operations.norm import norm
from pcot.xform import xformtype, XFormType


@xformtype
class XformNormImage(XFormType):
    """Normalize the image to a single range taken from all channels. Honours ROIs"""

    def __init__(self):
        super().__init__("normimage", "processing", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("", conntypes.IMG)
        self.hasEnable = True
        self.autoserialise = ('mode',)

    def createTab(self, n, w):
        return TabNorm(n, w)

    def init(self, node):
        node.mode = 0
        node.img = None

    def perform(self, node):
        # this uses the performOp function to wrap the "norm" operation function so that
        # it works in a node.
        operations.performOp(node, operations.norm.norm, mode=node.mode)


class TabNorm(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabnorm.ui')
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setPersister(node)
        self.w.mode.currentIndexChanged.connect(self.modeChanged)
        self.onNodeChanged()

    def modeChanged(self, i):
        self.node.mode = i
        self.changed()

    def onNodeChanged(self):
        self.w.mode.setCurrentIndex(self.node.mode)
        print("Node displ")
        self.w.canvas.display(self.node.img)
