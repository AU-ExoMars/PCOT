import pcot.ui.tabs


# this is a tab type for transforms which just display an image. They
# have one datum - "img" - in the node.

class TabImage(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabimage.ui')  # same UI as sink
        self.w.canvas.setPersister(node)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.display(self.node.img)
