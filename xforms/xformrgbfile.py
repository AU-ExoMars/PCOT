import os

from PyQt5 import QtCore
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QFileSystemModel

import ui
import ui.canvas
import ui.tabs
from pancamimage import ImageCube
from xform import xformtype, XFormType


@xformtype
class XformRGBFile(XFormType):
    """Load an RGB file for use as an image source."""

    def __init__(self):
        super().__init__("rgbfile", "source", "0.0.0")
        ## our connectors
        self.addOutputConnector("rgb", "imgrgb")
        self.autoserialise = ('fname',)

    def createTab(self, n, w):
        return TabRGBFile(n, w)

    def init(self, node):
        node.img = None
        node.fname = None

    def loadImg(self, node):
        # will throw exception if load failed
        img = ImageCube.load(node.fname, node.mapping)
        ui.log("Image {} loaded: {}".format(node.fname, img))
        node.img = img

    # the "perform" of a source is to read the image if one hasn't 
    # been loaded, and output the image data.
    def perform(self, node):
        if node.img is None and node.fname is not None:
            self.loadImg(node)
        node.setOutput(0, node.img)


class TabRGBFile(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabrgbfile.ui')
        # set up the file tree
        self.dirModel = QFileSystemModel()
        # pretty ugly way to get hold of the config, done to avoid cyclic imports
        print(ui.app.config.get('Locations', 'images'))
        self.dirModel.setRootPath(os.path.expanduser(ui.app.config.get('Locations', 'images')))
        self.dirModel.setNameFilters(["*.jpg", "*.png", "*.ppm", "*.tga", "*.tif"])
        self.dirModel.setNameFilterDisables(False)
        tree = self.w.treeView
        self.w.treeView.setModel(self.dirModel)

        idx = self.dirModel.index(QDir.currentPath())
        self.w.treeView.selectionModel().select(idx, QtCore.QItemSelectionModel.Select)
        self.w.treeView.setIndentation(10)
        self.w.treeView.setSortingEnabled(True)
        self.w.treeView.setColumnWidth(0, self.w.treeView.width() / 1.5)
        self.w.treeView.setColumnHidden(1, True)
        self.w.treeView.setColumnHidden(2, True)
        self.w.treeView.doubleClicked.connect(self.fileClickedAction)
        self.w.treeView.scrollTo(idx)
        self.w.canvas.setMapping(node.mapping)
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.display(self.node.outputs[0])

    # this sets the file IN THE NODE. We store all data in the node,
    # the tab is just a view on the node.
    def fileClickedAction(self, idx):
        if not self.dirModel.isDir(idx):
            self.node.img = None  # forces perform to reload
            # we use the relative path here, it's more right that using the absolute path
            # most of the time.
            fname = os.path.relpath(self.dirModel.filePath(idx))
            self.node.fname = fname
            # and tell it to perform (outputting the data)
            self.changed()
