"""The palette widget module, which handles the palette of
nodes on the right hand side."""

from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QSizePolicy, QAction

import pcot.macros as macros
from pcot.xform import XFormType, XFormException
import pcot.ui as ui

view = None

# The groups into which the buttons are sorted - it's a constant.
groups = ["source", "macros", "maths", "processing", "calibration", "data", "regions", "ROI edit", "utility"]


class PaletteButton(QtWidgets.QPushButton):
    """The palette items, which are buttons which can be either clicked or dragged (with RMB)"""

    def __init__(self, name, xformtype, view):
        """constructor, taking button name, xformtype, and view into which they should be inserted."""
        super().__init__(name)
        self.name = name
        self.view = view
        self.xformtype = xformtype
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        
        # The scrollbar actually overlays the scroll area, rather than sitting to the right
        # of it. That means the right hand edge of the buttons is overlaid by the scroll area.
        # To fix this, I get the "scroll bar extent" (how wide a vertical or how tall a horizontal
        # scroll bar is) and set the button style to add a margin to the right of that width, plus
        # whatever the left margin is (10 here).
        
        app = QtWidgets.QApplication.instance()
        barsize = app.style().pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent)

        self.setStyleSheet(f"margin: 2px {barsize+5}px 2px 5px; padding: 2px 5px 2px 5px")

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
            self.click()
        elif event.button() == Qt.RightButton:
            self.mousePos = event.pos()  # save click position for dragging

    def mouseMoveEvent(self, event):
        """handle mouse move for dragging with RMB"""
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

    def click(self):
        """handle a single LMB click"""
        # create a new item at a position decided by the scene
        try:
            scene = self.view.scene()
            scene.mark()
            node = scene.graph.create(self.name)
            node.xy = scene.getNewPosition()
            # rebuild the scene
            scene.rebuild()
            # and perform the node to get initial data
            node.graph.performNodes(node)
        except XFormException as e:
            ui.error(e.message)


class Palette:
    """the palette itself, which isn't a widget but a plain class containing all the necessary widgets etc."""

    def __init__(self, doc, scrollArea, scrollAreaContent, vw):
        """set up the scrolling palette as part of view initialisation, will populate with initial data"""
        self.doc = doc
        layout = QtWidgets.QVBoxLayout()
        scrollAreaContent.setLayout(layout)
        self.scrollAreaContent = scrollAreaContent
        self.view = vw
        self.layout = layout
        self.populate()

    def populate(self):
        """populate the palette with items"""

        grouplists = {x: [] for x in groups}
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
                b = PaletteButton(k, alltypes[k], self.view)
                if g == 'macros':
                    b.setStyleSheet("background-color:rgb(220,220,140)")
                self.layout.addWidget(b)
