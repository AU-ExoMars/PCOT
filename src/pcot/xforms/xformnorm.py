from pcot.datum import Datum
import pcot.operations as operations
import pcot.ui.tabs
from pcot.parameters.taggedaggregates import TaggedDictType
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

        self.params = TaggedDictType(
            mode=("Mode - nonzero means clamp, zero means normalise", int, 0)
        )

    def createTab(self, n, w):
        return TabNorm(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        # this uses the performOp function to wrap the "norm" operation function so that
        # it works in a node.
        operations.performOp(node, operations.norm.norm, clamp=node.params.mode)


class TabNorm(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabnorm.ui')
        self.w.mode.currentIndexChanged.connect(self.modeChanged)
        self.nodeChanged()

    def modeChanged(self, i):
        self.mark()
        self.node.params.mode = i
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.mode.setCurrentIndex(self.node.params.mode)
        self.w.canvas.display(self.node.getOutput(0, Datum.IMG))
