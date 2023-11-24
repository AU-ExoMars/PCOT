from pcot.datum import Datum
import pcot.operations as operations
import pcot.ui.tabs
from pcot.xform import xformtype, XFormType


@xformtype
class XformNormImage(XFormType):
    """
    Normalise the image to a single range taken from all channels. Honours ROIs. If you need to normalise
    each channel separately, use the norm() function in the "expr" node which has an optional argument for this."""

    def __init__(self):
        super().__init__("normimage", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.hasEnable = True
        self.autoserialise = ('mode',)

    def createTab(self, n, w):
        return TabNorm(n, w)

    def init(self, node):
        node.paintMode = 0
        node.img = None

    def perform(self, node):
        # this uses the performOp function to wrap the "norm" operation function so that
        # it works in a node.
        operations.performOp(node, operations.norm.norm, clamp=node.paintMode)


class TabNorm(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabnorm.ui')
        self.w.paintMode.currentIndexChanged.connect(self.modeChanged)
        self.nodeChanged()

    def modeChanged(self, i):
        self.mark()
        self.node.paintMode = i
        self.changed()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.paintMode.setCurrentIndex(self.node.paintMode)
        self.w.canvas.display(self.node.img)
