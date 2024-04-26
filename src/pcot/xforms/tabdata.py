import pcot.ui.tabs
from pcot.datum import Datum

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

    SRC_OUTPUT0 = 0     # if this is the source, use output 0 in the node to get data
    SRC_DATA = 1    # if this is the source, use the data field in the node to get data

    source: int     # one of the above options
    data: Datum     # the data to display if the source is SRC_DATA

    def __init__(self, node, w, src=SRC_OUTPUT0):
        super().__init__(w, node, 'tabdata.ui')
        self.source = src
        self.disptype = DATA
        self.w.dispTypeBox.currentIndexChanged.connect(self.dispTypeChanged)
        # these were inside onNodeChanged when out.isImage was true. I've moved them here
        # because really they should happen once, not every time the node changes, and it
        # should make no difference if an image is present or not.
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        # sync tab with node
        self.nodeChanged()

    def dispTypeChanged(self, i):
        # we won't serialise the display type - we could, but then node would need a display type.
        self.disptype = i
        self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        if self.source == self.SRC_OUTPUT0:
            out = self.node.getOutputDatum(0)
        elif self.source == self.SRC_DATA:
            out = self.node.data
        else:
            raise ValueError("Unknown source type")
        if out is not None:
            self.w.type.setText(str(out.tp))
            if self.disptype == SOURCES:
                # if we're displaying sources, we want to display the long form of the sources in the text.
                self.w.text.setText(generateIndenting(out.sources.long()))
                canvVis = False
            elif out.isImage():
                # otherwise if we're displaying an image datum, we want to display it in the canvas
                self.w.canvas.display(out.val)
                canvVis = True
            else:
                # otherwise we're displaying a non-image datum, so we want to display it in the text
                self.w.text.setText(str(out.val))
                canvVis = False
        else:
            self.w.type.setText("unconnected")
            self.w.text.setText("No data present")
            canvVis = False

        # set the visibility of the canvas and text widgets
        self.w.canvas.setVisible(canvVis)
        self.w.text.setVisible(not canvVis)

        # just making sure that we don't trigger a changed event when we change the combo box
        # which would cause an infinite loop
        with SignalBlocker(self.w.dispTypeBox):
            self.w.dispTypeBox.setCurrentIndex(self.disptype)
