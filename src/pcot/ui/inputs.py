import logging
import os
from pathlib import Path
from typing import List

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileSystemModel

import pcot
from pcot.ui import uiloader
from pcot.ui import theme

logger = logging.getLogger(__name__)


class MethodSelectButton(QtWidgets.QPushButton):
    """Subclass of button used for the buttons at the top of the input window for each method"""

    def __init__(self, w, m):
        """Method select buttons know about both the owning input window and the method"""
        super().__init__()
        self.window = w
        self.method = m
        self.setText(m.getName())
        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                                 QtWidgets.QSizePolicy.Policy.Maximum))
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
        textSize = metrics.size(Qt.TextFlag.TextShowMnemonic, self.text())
        size.setHeight(textSize.height() + 15)
        return size

    def showActive(self):
        """Colour the button to show that this method is active"""
        self.setStyleSheet(theme.methodButtonStyle(self.method.isActive()))


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
        central.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                                    QtWidgets.QSizePolicy.Policy.Expanding))
        self.setCentralWidget(central)
        self.setMinimumSize(1000, 780)

        # top box contains the buttons determining what sort of input this is
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        topBox = QtWidgets.QWidget()
        topBox.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                                   QtWidgets.QSizePolicy.Policy.Maximum))
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
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                if m.canUndo():
                    m.undo()
                    self.onUndoRedo()
            elif event.key() == Qt.Key.Key_Y:
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
        super().closeEvent(event)
        for w in self.widgets:
            w.onClose()
            w.deleteLater()     # delete all the bloody widgets
        self.widgets = []
        event.accept()

    def methodChanged(self):
        for w in self.widgets:
            active = w.method.isActive()
            w.setVisible(active)
            if active:
                w.syncIfNeeded()


# Widgets for viewing/controlling the Methods (i.e. input types within the Input)

class MethodWidget(QtWidgets.QWidget):
    """Superclass for the method widgets. Each method widget contains all the controls for an input method (and gets
    those controls from a UI file). See any of the subclasses for details."""
    method: 'InputMethod'

    def __init__(self, m):
        self.method = m
        self.openingWindow = False  # true if the window is opening
        self._synced = False  # has a real onInputChanged() sync ever happened for this widget?
        super().__init__()

    def onInputChanged(self):
        """implemented in subclasses, can be called when data changed from outside (deserialise, undo, redo)"""
        pass

    def _sync(self):
        """Actually perform a sync: run onInputChanged() (which may do disk I/O, pop dialogs,
        invalidate()+performGraph()) and remember that we've done so."""
        self.onInputChanged()
        self._synced = True

    def syncIfActive(self):
        """Call at the end of a widget's __init__, in place of an unconditional onInputChanged().
        Only syncs if this method is the active one when the window is opening - inactive methods'
        widgets are left unsynced until the user actually switches to them (see syncIfNeeded())."""
        if self.method.isActive():
            self._sync()

    def syncIfNeeded(self):
        """Call when this widget's method has just become the active one (button clicked).
        Performs the real sync only the first time; a widget that's already been synced is left
        alone so re-switching to it is instant and doesn't repeat disk I/O or dialogs."""
        if not self._synced:
            self._sync()

    def onUndoRedo(self):
        self._sync()
        if self.method.input.window is not None:
            self.method.input.window.methodChanged()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.method.undo()
                self.onUndoRedo()
            elif event.key() == Qt.Key.Key_Y:
                self.method.redo()
                self.onUndoRedo()

    def invalidate(self):
        if self.method.isActive():
            self.method.invalidate()

    def onClose(self):
        pass


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
        self.selDirButton.clicked.connect(self.selectDir)
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
        try:
            if self.method.fname and Path(self.method.fname).exists():
                    self.goto(self.method.fname)
            else:
                self.goto(root)
        except:     # if that path is weird...
            self.goto(root)

        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the document, which is stored in the manager,
        # which we get from the input, which we get from the method. Ugh.
        # Indirection, eh?
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

    def onClose(self):
        super().onClose()
        self.canvas.onClose()

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
            self.treeView.selectionModel().select(idx, QtCore.QItemSelectionModel.SelectionFlag.Select)
            self.treeView.scrollTo(idx)

    def lineToTree(self):
        txt = self.fileEdit.text()
        fname = os.path.realpath(os.path.expanduser(txt))
        if os.path.exists(fname):
            self.goto(fname)

    def selectDir(self):
        dirname = QtWidgets.QFileDialog.getExistingDirectory(None, 'Select directory',
                                                             self.fileEdit.text(),
                                                             options=pcot.config.getFileDialogOptions())

        if dirname:
            self.fileEdit.setText(dirname)
            self.lineToTree()

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
        layout.addWidget(QtWidgets.QLabel("No input method is in use."))
