from PySide6 import QtWidgets

import pcot.ui.tabs
from pcot.datum import Datum
from pcot.ui.datawidget import DataWidget
from pcot.ui.taggedaggregates import AggregateEditorWidget

# combo box values

DATA = 0
SOURCES = 1

class TabGeneric(pcot.ui.tabs.Tab):
    """this is a tab type for nodes which just display an image or other data, and have simple
    parameters. Normally this data comes from output 0 in the node, but it can be made to come
    from the "data" field of the node by setting the source in the constructor.
    This is useful when the node has no outputs, or when data to be shown is not that to be output.

    It can also be set to show extra controls at the top of the display which give the data
    type and let you switch between source and data view.

    Turning this off can be useful when space is at a premium - but you will lose the source display option.

    You can also disable the parameter editor.
    """

    SRC_OUTPUT0 = 0  # if this is the source, use output 0 in the node to get data
    SRC_DATA = 1  # if this is the source, use the data field in the node to get data

    source: int  # one of the above options
    data: Datum  # the data to display if the source is SRC_DATA

    def __init__(self, node, w, src=SRC_OUTPUT0, source_section=False, suppress_editor=False):
        super().__init__(w, node)
        # build the UI by hand!
        layout = QtWidgets.QHBoxLayout(self.w)
        self.w.setLayout(layout)

        splitter = QtWidgets.QSplitter(self.w)
        layout.addWidget(splitter)

        self.w.data = DataWidget(self.w, source_section)
        splitter.addWidget(self.w.data)

        if hasattr(node.type,"params") and node.type.params is not None and len(node.type.params)>0 and not suppress_editor:
            # we set internal_editor to True to avoid the editor having
            # an unreasonable minimum width
            self.editor = AggregateEditorWidget(node.params,
                                                handler=self,
                                                internal_editor=True)
            splitter.addWidget(self.editor)

        self.source = src
        self.disptype = DATA
        # sync tab with node
        self.nodeChanged()

    def onPostChange(self, _):
        # this is called when the AggregateEditorWidget changes any
        # parameter values, because its handler is set to self.
        self.changed()

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
