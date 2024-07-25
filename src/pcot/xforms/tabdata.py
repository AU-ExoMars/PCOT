from PySide2 import QtWidgets

import pcot.ui.tabs
from pcot.datum import Datum
from pcot.ui.datawidget import DataWidget

# combo box values
from pcot.utils import SignalBlocker
from pcot.utils.text import generateIndenting

DATA = 0
SOURCES = 1


class TabData(pcot.ui.tabs.Tab):
    """this is a tab type for nodes which just display an image or other data. Normally this data
    comes from output 0 in the node, but it can be made to come from the "data" field of the node
    by setting the source in the constructor. This is useful when the node has no outputs, or when
    data to be shown is not that to be output."""

    SRC_OUTPUT0 = 0  # if this is the source, use output 0 in the node to get data
    SRC_DATA = 1  # if this is the source, use the data field in the node to get data

    source: int  # one of the above options
    data: Datum  # the data to display if the source is SRC_DATA

    def __init__(self, node, w, src=SRC_OUTPUT0):
        super().__init__(w, node)
        # build the UI by hand!
        layout = QtWidgets.QVBoxLayout(self.w)
        self.w.setLayout(layout)
        self.w.data = DataWidget(self.w)
        layout.addWidget(self.w.data)

        self.source = src
        self.disptype = DATA
        # sync tab with node
        self.nodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle undo events which change the graph and nodes
        self.w.data.canvas.setNode(self.node)
        if self.source == self.SRC_OUTPUT0:
            out = self.node.getOutputDatum(0)
        elif self.source == self.SRC_DATA:
            out = self.node.data
        else:
            raise ValueError("Unknown source type")
        self.w.data.display(out)
