import ui,ui.tabs,ui.canvas

# this is a tab type for transforms which just display an image. They
# have one datum - "img" - in the node.

class TabImage(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabimage.ui') # same UI as sink
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.display(self.node.img)

