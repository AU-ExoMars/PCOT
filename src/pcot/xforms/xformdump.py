from pcot.datum import Datum
from pcot.utils.text import generateIndenting
from pcot.xform import xformtype, XFormType
import pcot.ui.tabs

# combo box values
DATA = 0
SOURCES = 1


# Simple data dumper: just prints a string of its output
# into its window

@xformtype
class XFormDump(XFormType):
    """Simple data dump: prints a string of its output into its window. Useful for outputting spectra as CSV."""

    def __init__(self):
        super().__init__("dump", "data", "0.0.0")
        self.addInputConnector("any", Datum.ANY)
        self.autoserialise += ('disptype', )

    def createTab(self, n, w):
        return TabDump(n, w)

    def init(self, node):
        node.data = None
        node.tp = "unconnected"
        node.disptype = DATA

    def perform(self, node):
        d = node.getInput(0)
        if d is None:
            node.tp = "unconnected"
            node.data = "None"
        else:
            node.tp = d.tp
            if node.disptype == DATA:
                node.data = str(d.val)
            elif node.disptype == SOURCES:
                node.data = generateIndenting(d.sources.long())


class TabDump(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabdump.ui')
        self.w.dispTypeBox.currentIndexChanged.connect(self.dispTypeChanged)
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.type.setText(str(self.node.tp))
        self.w.text.setPlainText(str(self.node.data))
        self.w.dispTypeBox.setCurrentIndex(self.node.disptype)

    def dispTypeChanged(self, i):
        self.node.disptype = i
        self.changed()

