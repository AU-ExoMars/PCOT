import logging
import os
from typing import List

from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFileSystemModel

import pcot
from pcot.ui import uiloader

logger = logging.getLogger(__name__)


class MethodSelectButton(QtWidgets.QPushButton):
    """Subclass of button used for the buttons at the top of the input window for each method"""

    def __init__(self, w, m):
        """Method select buttons know about both the owning input window and the method"""
        super().__init__()
        self.window = w
        self.method = m
        self.setText(m.getName())
        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                 QtWidgets.QSizePolicy.Maximum))
        self.clicked.connect(self.onClick)

    def onClick(self):
        """When clicked, make this method active"""
        self.window.input.selectMethod(self.method)
        self.window.showActiveMethod()

    def sizeHint(self):
        """The buttons are always rather too tall and I have no idea why. To fix this, I'm setting the height
           to the required height for the text. There must be a better way. For one thing, adding padding to that
           value sometimes doesn't work."""
        size = super().sizeHint()
        metrics = QtGui.QFontMetrics(self.font())
        textSize = metrics.size(Qt.TextShowMnemonic, self.text())
        size.setHeight(textSize.height() + 15)
        return size

    def showActive(self):
        """Colour the button to show that this method is active"""
        if self.method.isActive():
            r, g, b = 200, 200, 255
        else:
            r, g, b = 200, 200, 200
        self.setStyleSheet(
            f"border-style: outset; padding: 40px; border-width:1px; border-color:black; background-color:rgb({r},{g},{b})")


class InputWindow(QtWidgets.QMainWindow):
    """The window for each input - consists of buttons to select a method and a group of widgets, one for each method,
    only one of which is visible."""
    input: 'Input'
    widgets: List['MethodWidget']
    buttons: List[MethodSelectButton]

    def __init__(self, inp: 'Input'):
        super().__init__()
        self.input = inp
        self.widgets = []
        self.buttons = []

        central = QtWidgets.QWidget()
        central.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                                    QtWidgets.QSizePolicy.Expanding))
        self.setCentralWidget(central)
        self.setMinimumSize(1000, 700)

        # top box contains the buttons determining what sort of input this is
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        topBox = QtWidgets.QWidget()
        topBox.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                   QtWidgets.QSizePolicy.Preferred))
        topBoxLayout = QtWidgets.QHBoxLayout()
        topBox.setLayout(topBoxLayout)
        layout.addWidget(topBox)
        #        topBox.setMaximumHeight(50)

        for m in self.input.methods:
            m.openingWindow = True  # this avoids graph running when the window is opening
            widget = m.createWidget()
            m.openingWindow = False
            if widget is not None:
                b = MethodSelectButton(self, m)
                self.buttons.append(b)
                topBoxLayout.addWidget(b)
                self.widgets.append(widget)
                layout.addWidget(widget)

                if not m.isActive():
                    widget.setVisible(False)

        self.showActiveMethod()
        self.show()

    def showActiveMethod(self):
        for b in self.buttons:
            b.showActive()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        m = self.input.getActive()
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                if m.canUndo():
                    m.undo()
                    self.onUndoRedo()
            elif event.key() == Qt.Key_Y:
                if m.canRedo():
                    m.redo()
                    self.onUndoRedo()

    def onUndoRedo(self):
        for w in self.widgets:
            if w.method.isActive():
                w.onUndoRedo()

    def closeEvent(self, event):
        logger.debug("Closing input window")
        self.input.onWindowClosed()
        event.accept()

    def methodChanged(self):
        for w in self.widgets:
            w.setVisible(w.method.isActive())


# Widgets for viewing/controlling the Methods (i.e. input types within the Input)

class MethodWidget(QtWidgets.QWidget):
    """Superclass for the method widgets. Each method widget contains all the controls for an input method (and gets
    those controls from a UI file). See any of the subclasses for details."""
    method: 'InputMethod'

    def __init__(self, m):
        self.method = m
        self.openingWindow = False  # true if the window is opening
        super().__init__()

    def onInputChanged(self):
        """implemented in subclasses, can be called when data changed from outside (deserialise, undo, redo)"""
        pass

    def onUndoRedo(self):
        self.onInputChanged()
        if self.method.input.window is not None:
            self.method.input.window.methodChanged()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                self.method.undo()
                self.onUndoRedo()
            elif event.key() == Qt.Key_Y:
                self.method.redo()
                self.onUndoRedo()

    def invalidate(self):
        if self.method.isActive():
            self.method.invalidate()


class TreeMethodWidget(MethodWidget):
    """This class is for displaying input methods which rely on a tree view of files,
    and which use single files - ENVI and RGB are examples."""

    def __init__(self, m, uiFile: str, filterList: List[str]):
        super().__init__(m)
        uiloader.loadUi(uiFile, self)
        # set up the file tree
        self.dirModel = QFileSystemModel()
        # pretty ugly way to get hold of the config, done to avoid cyclic imports
        root = os.path.expanduser(pcot.config.getDefaultDir('images'))
        if not os.path.isdir(root):
            root = os.path.expanduser("~")
        self.fileEdit.setText(root)
        self.dirModel.setRootPath(root)
        self.dirModel.setNameFilters(filterList)
        self.dirModel.setNameFilterDisables(False)
        self.treeView.setModel(self.dirModel)
        self.treeView.setMinimumSize(300, 500)
        self.treeView.setMaximumHeight(700)

        self.treeView.setIndentation(10)
        self.treeView.setSortingEnabled(True)
        self.treeView.setColumnWidth(0, self.treeView.width() / 1.5)
        self.treeView.setColumnHidden(1, True)
        self.treeView.setColumnHidden(2, True)
        self.treeView.doubleClicked.connect(self.fileDoubleClickedAction)
        self.fileEdit.editingFinished.connect(self.lineToTree)
        self.treeView.clicked.connect(self.fileClickedAction)
        self.goto(root)

        self.canvas.setMapping(m.mapping)
        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the document, which is stored in the manager,
        # which we get from the input, which we get from the method. Ugh.
        # Indirection, eh?
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        self.onInputChanged()

    def goto(self, filename):
        """Filename could be a file or directory - we should scroll to it, and select it if it's a file"""
        if os.path.isfile(filename):
            dirname = os.path.dirname(filename)
        elif os.path.isdir(filename):
            dirname = filename
            filename = None
        else:
            dirname = os.path.expanduser("~")
        logger.debug(f"FILENAME IS {filename}, DIRNAME IS {dirname}")
        # find index of directory
        idx = self.dirModel.index(dirname)
        # expand and scroll to it
        self.treeView.setExpanded(idx, True)
        # and select the file (if one is selected)
        self.treeView.scrollTo(idx)

        if filename is not None and os.path.isfile(filename):
            idx = self.dirModel.index(filename)
            self.treeView.selectionModel().select(idx, QtCore.QItemSelectionModel.Select)
            self.treeView.scrollTo(idx)

    def lineToTree(self):
        txt = self.fileEdit.text()
        fname = os.path.realpath(os.path.expanduser(txt))
        if os.path.exists(fname):
            self.goto(fname)

    def fileClickedAction(self, idx):
        name = os.path.realpath(self.dirModel.filePath(idx))
        self.fileEdit.setText(name)

    def fileDoubleClickedAction(self, idx):
        if not self.dirModel.isDir(idx):
            self.method.mark()
            self.method.img = None
            self.method.fname = os.path.realpath(self.dirModel.filePath(idx))
            self.method.get()
            pcot.config.setDefaultDir('images', os.path.dirname(self.method.fname))
            self.onInputChanged()


class NullMethodWidget(MethodWidget):
    """This method widget does nothing at all."""

    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtWidgets.QLabel("NULL INPUT"))


class PlaceholderMethodWidget(MethodWidget):
    """This method widget does nothing at all, but differently."""

    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        text = m.getName() + " PLACEHOLDER"
        layout.addWidget(QtWidgets.QLabel(text))
