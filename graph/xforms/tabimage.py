import ui.tabs,ui.canvas

# this is a tab type for transforms which just display an image. They
# have one datum - "img" - in the node.

class TabImage(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabimage.ui') # same UI as sink
        self.canvas = self.getUI(ui.canvas.Canvas,'canvas')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.canvas.display(self.node.img)

