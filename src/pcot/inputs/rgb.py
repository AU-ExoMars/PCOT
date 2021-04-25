## the RGB file input method
import os
from typing import Optional

from PyQt5 import QtCore, uic
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QFileSystemModel

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.pancamimage import ImageCube, ChannelMapping
from pcot.ui.inputs import MethodWidget


class RGBInputMethod(InputMethod):
    img: Optional[ImageCube]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        # will throw exception if load failed
        img = ImageCube.load(self.fname, self.mapping)
        ui.log("Image {} loaded: {}".format(self.fname, img))
        self.img = img

    def get(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "RGB"

    def createWidget(self):
        return RGBMethodWidget(self)

    def serialise(self):
        return self.fname

    def deserialise(self, data):
        self.fname = data


class RGBMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uic.loadUi(pcot.getAssetAsFile('tabrgbfile.ui'), self)
        # set up the file tree
        self.dirModel = QFileSystemModel()
        # pretty ugly way to get hold of the config, done to avoid cyclic imports
        print(pcot.config.get('Locations', 'images'))
        self.dirModel.setRootPath(os.path.expanduser(pcot.config.get('Locations', 'images')))
        self.dirModel.setNameFilters(["*.jpg", "*.png", "*.ppm", "*.tga", "*.tif"])
        self.dirModel.setNameFilterDisables(False)
        tree = self.treeView
        self.treeView.setModel(self.dirModel)
        self.treeView.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)

        idx = self.dirModel.index(QDir.currentPath())
        self.treeView.selectionModel().select(idx, QtCore.QItemSelectionModel.Select)
        self.treeView.setIndentation(10)
        self.treeView.setSortingEnabled(True)
        self.treeView.setColumnWidth(0, self.treeView.width() / 1.5)
        self.treeView.setColumnHidden(1, True)
        self.treeView.setColumnHidden(2, True)
        self.treeView.doubleClicked.connect(self.fileClickedAction)
        self.treeView.scrollTo(idx)
        self.canvas.setMapping(m.mapping)
        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the manager, which we get from the input,
        # which we get from the method. Ugh.
        self.canvas.setGraph(self.method.input.mgr.graph)
        self.onInputChanged()

    def onInputChanged(self):
        self.canvas.display(self.method.img)
        self.method.input.performGraph()

    def fileClickedAction(self, idx):
        if not self.dirModel.isDir(idx):
            self.method.img = None
            self.method.fname = os.path.relpath(self.dirModel.filePath(idx))
            self.method.get()
            self.onInputChanged()



