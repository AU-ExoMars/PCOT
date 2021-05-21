import os
from typing import List

from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QFileSystemModel

import pcot


class MethodSelectButton(QtWidgets.QPushButton):
    def __init__(self, inp, m):
        super().__init__()
        self.input = inp
        self.method = m
        self.setText(m.getName())
        self.clicked.connect(self.onClick)

    def onClick(self):
        self.input.selectMethod(self.method)


class InputWindow(QtWidgets.QMainWindow):
    input: 'Input'
    widgets: List['MethodWidget']

    def __init__(self, inp: 'Input'):
        super().__init__()
        self.input = inp
        self.widgets = []

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # top box contains the buttons determining what sort of input this is
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        topBox = QtWidgets.QWidget()
        topBoxLayout = QtWidgets.QHBoxLayout()
        topBox.setLayout(topBoxLayout)
        layout.addWidget(topBox)
        topBox.setMaximumHeight(50)

        for m in self.input.methods:
            b = MethodSelectButton(self.input, m)
            topBoxLayout.addWidget(b)
            m.openingWindow = True
            widget = m.createWidget()
            m.openingWindow = False
            self.widgets.append(widget)
            layout.addWidget(widget)

            if not m.isActive():
                widget.setVisible(False)

        self.show()

    def closeEvent(self, event):
        print("Closing input window")
        self.input.onWindowClosed()
        event.accept()

    def methodChanged(self):
        for w in self.widgets:
            w.setVisible(w.method.isActive())


# Widgets for viewing/controlling the Methods (i.e. input types within the Input)

class MethodWidget(QtWidgets.QWidget):
    method: 'InputMethod'

    def __init__(self, m):
        self.method = m
        self.openingWindow = False   # true if the window is opening
        super().__init__()

    def invalidate(self):
        self.method.invalidate()


# This class is for displaying input methods which rely on a tree view of files,
# and which use single files - ENVI and RGB are examples.
class TreeMethodWidget(MethodWidget):
    def __init__(self, m, uiFile: str, filterList: List[str]):
        super().__init__(m)
        uic.loadUi(pcot.config.getAssetAsFile(uiFile), self)
        # set up the file tree
        self.dirModel = QFileSystemModel()
        # pretty ugly way to get hold of the config, done to avoid cyclic imports
        root = os.path.expanduser(pcot.config.locations.get('images'))
        self.dirModel.setRootPath(root)
        self.dirModel.setNameFilters(filterList)
        self.dirModel.setNameFilterDisables(False)
        self.treeView.setModel(self.dirModel)
        self.treeView.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)

        # find index of directory
        idx = self.dirModel.index(root)
        # expand and scroll to it
        self.treeView.setExpanded(idx, True)
        # and select the file (if one is selected)
        self.treeView.scrollTo(idx)
        if self.method.fname is not None:
            idx = self.dirModel.index(self.method.fname)
            self.treeView.selectionModel().select(idx, QtCore.QItemSelectionModel.Select)
            self.treeView.scrollTo(idx)

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
        self.canvas.setPersister(m)

        self.onInputChanged()

    def fileClickedAction(self, idx):
        if not self.dirModel.isDir(idx):
            self.method.img = None
            self.method.get()
            self.method.fname = os.path.realpath(self.dirModel.filePath(idx))
            pcot.config.locations['images'] = os.path.dirname(self.method.fname)
            pcot.config.save()
            self.onInputChanged()


class NullMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtWidgets.QLabel("NULL INPUT"))


class PlaceholderMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        text = m.getName() + " PLACEHOLDER"
        layout.addWidget(QtWidgets.QLabel(text))
