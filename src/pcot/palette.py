"""The palette widget module, which handles the palette of
nodes on the right hand side."""

from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QMessageBox, QSizePolicy, QAction

import pcot.assets
import pcot.macros as macros
from pcot.ui.collapser import Collapser
from pcot.xform import XFormType, XFormException
import pcot.ui as ui

import logging 

logger = logging.getLogger(__name__)

view = None

# The groups into which the buttons are sorted - it's a constant.
groups = ["source", "macros", "maths", "processing", "calibration", "data", "regions", "ROI edit", "utility", "testing"]



class PaletteButton(QtWidgets.QPushButton):
    """The palette items, which are buttons which can be either clicked or dragged (with RMB)"""

    def __init__(self, name, xformtype, view):
        """constructor, taking button name, xformtype, and view into which they should be inserted."""
        super().__init__(name)
        self.name = name
        self.view = view
        self.xformtype = xformtype
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.customContextMenuRequested.connect(self.contextMenu)

    def contextMenu(self, e):
        menu = QtWidgets.QMenu()
        # we only add some of these
        openProtoAct = QAction("Open prototype")
        deleteMacroAct = QAction("Delete macro")
        helpAct = QAction("Help")

        if isinstance(self.xformtype, macros.XFormMacro):
            menu.addAction(openProtoAct)
            menu.addAction(deleteMacroAct)
        else:
            menu.addAction(helpAct)

        act = menu.exec_(self.mapToGlobal(e))
        if act == helpAct:
            self.view.window.openHelp(self.xformtype)
        elif act == openProtoAct:
            ui.mainwindow.MainUI(self.xformtype.doc,
                                 macro=self.xformtype,
                                 doAutoLayout=False)
        elif act == deleteMacroAct:
            if QMessageBox.question(self.parent(), "Delete macro", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                macros.XFormMacro.deleteMacro(self.xformtype)
                ui.mainwindow.MainUI.rebuildPalettes()

    # drag handling: nabbed from
    # https://stackoverflow.com/questions/57224812/pyqt5-move-button-on-mainwindow-with-drag-drop
    # This stuff interacts with the graph view (graphview.py)

    def mousePressEvent(self, event):
        """handle a mouse down event"""
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.mousePos = event.pos()  # save click position for dragging

    def mouseMoveEvent(self, event):
        """handle mouse move for dragging with LMB.
        Note that the node is actually created when the box is dropped in GraphView.dropEvent.
        """
        if event.buttons() != QtCore.Qt.LeftButton:
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

    def click(self):
        """handle a single LMB click"""
        # create a new item at a position decided by the scene
        try:
            scene = self.view.scene()
            scene.mark()
            node = scene.graph.create(self.name)
            # rebuild the scene
            scene.rebuild()
            # and perform the node to get initial data
            node.graph.performNodes(node)
        except XFormException as e:
            ui.error(e.message)


class Palette:
    """the palette itself, which isn't a widget but a plain class containing all the necessary widgets etc."""

    def __init__(self, doc, collapser: Collapser, collapseButton: QtWidgets.QPushButton, vw):
        """set up the scrolling palette as part of view initialisation, will populate with initial data"""
        self.doc = doc
        self.view = vw
        self.collapser = collapser
        self.collapseButton = collapseButton
        self.namesByGroup = {}    # list of name per group
        self.widgetsByName = {}     # actual widgets by name
        self.populate()

    def populate(self):
        """populate the palette with items"""

        self.namesByGroup = {x: [] for x in groups}
        # we want the keys in sorted order, and the keys come from both the global
        # types and the macros for this document. This is a dict merge - in 3.9+ we
        # could use the a|b syntax.
        alltypes = {**XFormType.all(), **self.doc.macros}
        ks = sorted(alltypes.keys())
        # add xformtypes to a list for each group
        for k in ks:
            v = alltypes[k]
            if v.group not in groups:
                # "hidden" is a special group which doesn't appear in the palette, used for 
                # things like macro connectors.
                if v.group != 'hidden':
                    raise Exception("node '{}' not in any group defined in palette.py!".format(k))
            else:
                self.namesByGroup[v.group].append(k)

        self.collapser.clear()
        self.setCollapseButton()


        # add buttons and separators for each group
        for g in groups:
            layout = QtWidgets.QVBoxLayout()
            layout.setContentsMargins(2, 5, 2, 5)
            for k in self.namesByGroup[g]:
                b = PaletteButton(k, alltypes[k], self.view)
                self.widgetsByName[k] = b
                if g == 'macros':
                    b.setStyleSheet("background-color:rgb(220,220,140)")
                layout.addWidget(b)
            self.collapser.addSection(g, layout)
        self.collapser.end()

    def paletteSearchChanged(self, text):
        # hide widgets which don't have the text, if there is one
        is_vis = {}
        for k,v in self.widgetsByName.items():
            visible = text == "" or text in k
            is_vis[k] = visible
            v.setVisible(visible)

        # if a group has no widgets, hide the group. If it does, expand the group.
        for k,v in self.namesByGroup.items():
            visible = any(is_vis[v] for v in v)
            self.collapser.setSectionVisible(k, visible)
            if visible:
                    self.collapser.forceOpen(k)

        self.collapser.update()

    def paletteCollapseExpandAll(self):
        self.collapser.collapseExpandAll()
        self.setCollapseButton()

    def setCollapseButton(self):
        if self.collapser.shouldCollapseWhenButtonClicked():
            icon = pcot.assets.Icons.get("chevrons-up.svg")
        else:
            icon = pcot.assets.Icons.get("chevrons-down.svg")
        self.collapseButton.setIcon(icon)