import pcot.ui.tabs
from pcot.datum import Datum


class TabImage(pcot.ui.tabs.Tab):
    """this is a tab type for transforms which just display an image. They
    have one datum - "out" - in the node."""

    def __init__(self, node, w):
        super().__init__(w, node, 'tabimage.ui')  # same UI as sink
        # sync tab with node
        self.nodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        out = self.node.out
        if out is not None:
            if out.tp == Datum.IMG:
                self.w.canvas.setMapping(self.node.mapping)
                self.w.canvas.setGraph(self.node.graph)
                self.w.canvas.setPersister(self.node)
                self.w.canvas.display(self.node.out.val)
            else:
                # TODO display other data types
                pass
