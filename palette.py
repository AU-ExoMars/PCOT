## @package palette
# The palette widget package, which handles the palette of
# nodes on the right hand side.

from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

import macros
from xform import XFormType
from macros import XFormMacro
import ui

view = None

## The groups into which the buttons are sorted - it's a constant.
groups = ["source", "macros", "maths", "processing", "calibration", "data", "colour", "regions", "utility"]


## The palette items, which are buttons which can be either clicked or dragged (with RMB)

class PaletteButton(QtWidgets.QPushButton):
    ## constructor, taking button name, xformtype, and view into which they should be inserted.
    def __init__(self, name, xformtype, view):
        super().__init__(name)
        self.name = name
        self.view = view
        self.xformtype = xformtype
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)

    def contextMenu(self, e):
        menu = QtWidgets.QMenu()
        if isinstance(self.xformtype, XFormMacro):
            openProtoAct = menu.addAction("Open prototype")
            deleteMacroAct = menu.addAction("Delete macro")
            act = menu.exec_(self.mapToGlobal(e))
            if act == openProtoAct:
                ui.mainwindow.MainUI.createMacroWindow(self.xformtype, False)
            elif act == deleteMacroAct:
                if QMessageBox.question(self.parent(), "Delete macro", "Are you sure?",
                                        QMessageBox.Yes | QMessageBox.No):
                    macros.XFormMacro.deleteMacro(self.xformtype)
                    ui.mainwindow.MainUI.rebuildPalettes()

    # drag handling: nabbed from
    # https://stackoverflow.com/questions/57224812/pyqt5-move-button-on-mainwindow-with-drag-drop
    # This stuff interacts with the graph view (graphview.py)

    ## handle a mouse down event
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.click()
        elif event.button() == Qt.RightButton:
            self.mousePos = event.pos()  # save click position for dragging

    ## handle mouse move for dragging with RMB
    def mouseMoveEvent(self, event):
        if event.buttons() != QtCore.Qt.RightButton:
            return
        mimeData = QtCore.QMimeData()
        # create a byte array and a stream that is used to write into
        byteArray = QtCore.QByteArray()
        stream = QtCore.QDataStream(byteArray, QtCore.QIODevice.WriteOnly)
        stream.writeQString(self.name)
        mimeData.setData('data/palette', byteArray)
        drag = QtGui.QDrag(self)
        # add a pixmap of the widget to show what's actually moving
        drag.setPixmap(self.grab())
        drag.setMimeData(mimeData)
        # set the hotspot according to the mouse press position
        drag.setHotSpot(self.mousePos - self.rect().topLeft())
        drag.exec_(Qt.MoveAction)

        ## handle a single LMB click

    def click(self):
        # create a new item at a position decided by the scene
        node = self.view.scene().graph.create(self.name)
        node.xy = self.view.scene().getNewPosition()
        # rebuild the scene
        self.view.scene().rebuild()
        # and perform the node to get initial data
        node.graph.performNodes(node)


## the palette itself, which isn't a widget but a plain class containing all the necessary
# widgets etc.

class Palette:
    ## set up the scrolling palette as part of view initialisation, will populate
    # with initial data
    def __init__(self, scrollArea, scrollAreaContent, view):
        layout = QtWidgets.QVBoxLayout()
        scrollAreaContent.setLayout(layout)
        scrollArea.setMinimumWidth(150)
        self.scrollAreaContent = scrollAreaContent
        self.view = view
        self.layout = layout
        self.populate()

    ## populate the palette with items
    def populate(self):
        grouplists = {x: [] for x in groups}
        # we want the keys in sorted order
        all = XFormType.all()
        ks = sorted(all.keys())
        # add xformtypes to a list for each group
        for k in ks:
            v = all[k]
            if not v.group in groups:
                # "hidden" is a special group which doesn't appear in the palette, used for 
                # things like macro connectors.
                if v.group != 'hidden':
                    raise Exception("node '{}' not in any group defined in palette.py!".format(k))
            else:
                grouplists[v.group].append(k)

        # clear previous buttons and seps - we do this by going
        # backwards (so we keep the indices the same) and setting
        # each item's parent to none. Ugh.
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)

            # add buttons and separators for each group
        for g in groups:
            sep = QtWidgets.QLabel(g)
            sep.setStyleSheet("background-color:rgb(200,200,200)")
            self.layout.addWidget(sep)
            for k in grouplists[g]:
                v = all[k]
                b = PaletteButton(k, all[k], self.view)
                if g == 'macros':
                    b.setStyleSheet("background-color:rgb(220,220,140)")
                self.layout.addWidget(b)
