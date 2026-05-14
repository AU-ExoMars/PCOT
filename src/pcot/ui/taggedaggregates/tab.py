"""
A simple editor tab for a node with TaggedDict parameters.
"""

from pcot.datum import Datum
from pcot.ui.tabs import Tab
from pcot.ui.taggedaggregates import AggregateEditorWidget


class TabAggregate(Tab):
    def __init__(self, node, window):
        """Initialise the widget for this node"""
        super().__init__(window, node, "tabaggregate.ui")
        self.paramLayout = self.w.params.layout()
        self.updateParameters()
        self.w.canvas.setNode(node)
        self.nodeChanged()

    def updateParameters(self):
        if old := self.paramLayout.takeAt(0):
            # if there's already a parameter editor, delete it.
            old.widget().deleteLater()
        # create a new one
        paramEditor = AggregateEditorWidget(self.node.params, internal_editor=True, handler=self)
        self.paramLayout.addWidget(paramEditor)

    def onPreChange(self, node):
        pass

    def onPostChange(self,node):
        self.changed()

    def onNodeChanged(self):
        """This is called when a node changes, and is where we update the tab from the node."""
        # Update the canvas with the image in the node.
        # some setup stuff first. We have to do this here, not in the init, because
        # whenever we undo we get an entirely new graph (that's how undo works!)
        # Bear this in mind - self.node will change when you undo.
        self.w.canvas.setNode(self.node)
        # then display the image
        img = self.node.getOutput(0, Datum.IMG)
        self.w.canvas.display(img)
