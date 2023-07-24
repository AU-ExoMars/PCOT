"""This node manages several ROIs, allows editing, and combines them with an expression. Much more convenient
than using multiple ROI and expr nodes with an importroi node."""
from copy import copy
from functools import partial

from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QMessageBox, QInputDialog
from PySide2.QtCore import QModelIndex, Signal, QAbstractTableModel, Qt

import pcot.rois
import pcot.ui
from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.imagecube import ImageCube
from pcot.sources import nullSourceSet
from pcot.ui.tabs import Tab
from pcot.xform import xformtype, XFormType, XFormException


def getROIName(i):
    return chr(97 + i) if i < 26 else f"roi{i}"


@xformtype
class XFormROIExpr(XFormType):
    def __init__(self):
        super().__init__("roiexpr", "regions", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addInputConnector("p", Datum.ROI)
        self.addInputConnector("q", Datum.ROI)
        self.addInputConnector("r", Datum.ROI)
        self.addOutputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.ROI)
        self.autoserialise += ('expr',)

    def createTab(self, n, w):
        return TabROIExpr(n, w)

    def init(self, node):
        node.rois = []
        node.editors = dict()
        node.expr = ""
        node.selected = None
        node.selColour = (0, 1, 0)  # colour of selected ROI
        node.unselColour = (0, 1, 1)  # colour of unselected ROI
        node.outColour = (1, 1, 0)  # colour of output ROI
        node.hideROIs = False  # hide individual ROIs
        node.brushSize = 20  # scale of 0-99 i.e. a slider value. Converted to pixel radius in getRadiusFromSlider()
        node.previewRadius = None  # see xformpainted.

        self.autoserialise = ('selColour', 'unselColour', 'outColour', 'expr', 'hideROIs', 'previewRadius')

    def serialise(self, node):
        return {'rois': [(r.tpname, r.serialise()) for r in node.rois]}

    def deserialise(self, node, d):
        node.rois = [pcot.rois.deserialise(r, dat) for r, dat in d['rois']]

    def perform(self, node):
        img: ImageCube = node.getInput(0, Datum.IMG)

        #
        # All this code assumes that there are no sources in the ROIs it uses.
        #

        node.img = None
        node.roi = None
        outROIDatum = Datum.null

        # this colour is used for painted node preview.
        node.colour = node.selColour

        # must be an image, and must be an expression
        if img is not None:
            # and painted ROIs  need to know the image size too
            for r in node.rois:
                if isinstance(r, pcot.rois.ROIPainted):
                    r.setImageSize(img.w, img.h)
            img = img.copy()
            node.previewRadius = pcot.rois.getRadiusFromSlider(node.brushSize, img.w, img.h)
            if len(node.expr.strip()) > 0:
                # we create a new parser here, because we want it to be empty of ROIs etc.
                parser = ExpressionEvaluator()
                for i, r in enumerate(node.rois):
                    # register the ROIs into the parser (or rather lambdas that return datums)
                    roiname = getROIName(i)
                    # patch image size into the ROI so we can do negation
                    node.rois[i].setContainingImageDimensions(img.w, img.h)
                    # Register a variable which returns an ROI datum for that ROI
                    # *shakes fist at late-binding closures*
                    f = partial(lambda ii: Datum(Datum.ROI, node.rois[ii], sources=nullSourceSet), i)
                    parser.registerVar(roiname, f'value of ROI {i}', f)
                # might be useful to have the input image there too
                parser.registerVar('img', 'input image', lambda: Datum(Datum.IMG, img))
                # and three extra ROI inputs that might come from other data

                # this function gets an ROI input but patches the image width and height
                # into that ROI, so we can do daft stuff like negating ROIs.
                def getROIInput(i):
                    # ugly, but we need to access this to get the sources
                    d: Datum = node.getInput(i)
                    # and then immediately do this to get the actual ROI even if I'm doing work again.
                    rr = node.getInput(i, Datum.ROI)
                    if rr is None:
                        return Datum.null
                    else:
                        rr = copy(rr)
                        rr.setContainingImageDimensions(img.w, img.h)
                        return Datum(Datum.ROI, rr, sources=d.sources)

                parser.registerVar("p", "ROI input p", lambda: getROIInput(1))
                parser.registerVar("q", "ROI input q", lambda: getROIInput(1))
                parser.registerVar("r", "ROI input r", lambda: getROIInput(1))

                # now execute the expression and get it back as an ROI
                res = parser.run(node.expr)
                node.roi = res.get(Datum.ROI)
                # set its colour
                if node.roi is not None:
                    node.roi.drawBox = False
                    node.roi.colour = node.outColour
                    # impose that ROI on the image - REMOVING existing ROIs
                    img.rois = [node.roi]
                    outROIDatum = Datum(Datum.ROI, node.roi, node.roi.sources)
            # impose the individual ROIs as annotations
            if not node.hideROIs:
                for i, r in enumerate(node.rois):
                    r.colour = node.selColour if i == node.selected else node.unselColour
                img.annotations = node.rois
            # set mapping from node
            img.setMapping(node.mapping)
            # 'img' so far is the image we are going to display.
            node.img = img
            # but the image we are going to output is going to be different - it will have no annotations
            # because we don't want to see the sub-ROIs in the descendants.
            img = img.shallowCopy(copyAnnotations=False)

        outImgDatum = Datum(Datum.IMG, img)
        node.setOutput(0, outImgDatum)
        node.setOutput(1, outROIDatum)

    def uichange(self, node):
        """This might seem a bit weird, calling perform when a changed(uiOnly=True) happens - but while this will
        recalculate the entire node just to draw the UI elements again, it will not cause child nodes to run."""
        self.perform(node)

    def getROIDesc(self, node):
        return "no ROI" if node.roi is None else node.roi.details()

    def getMyROIs(self, node):
        """If this node creates an ROI or ROIs, return it/them as a list, otherwise None (not an empty list)"""
        return [node.roi]


COLNAMES = ["type", "info"]


class Model(QAbstractTableModel):
    """The model is what interfaces the table view to the data in the node's roi list. It also creates an editor
    for all existing rois if it's been initialised from an existing node (as would happen in deserialisation)"""
    changed = Signal()

    def __init__(self, tab, node):
        super().__init__()
        self.columnItems = False
        self.tab = tab
        self.node = node
        # create editors for existing nodes
        for r in self.node.rois:
            self.node.editors[r] = r.createEditor(tab)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLNAMES[section]
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return getROIName(section)  # index number to a,b,c,d...
        return super().headerData(section, orientation, role)

    def rowCount(self, index):
        return len(self.node.rois)

    def columnCount(self, index):
        return len(COLNAMES)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            item = index.row()
            field = index.column()
            roi = self.node.rois[item]

            if field == 0:
                return roi.tpname
            elif field == 1:
                return str(roi)

    def add_item(self, sourceIndex=None):
        n = len(self.node.rois)
        if sourceIndex is None:
            # pick an ROI - this is a dict of name to class
            choices = {x.tpname: x for x in pcot.rois.ROI.__subclasses__()}
            k, ok = QInputDialog.getItem(None, "Select a type", "type", list(choices.keys()), 0, False)
            if not ok:
                return
            # construct the new item
            new = choices[k]()
        else:
            new = self.node.rois[sourceIndex].copy()
        new.colour = (0, 1, 0)  # green by default
        # create an editor for the new ROI
        self.node.editors[new] = new.createEditor(self.tab)
        self.beginInsertRows(QModelIndex(), n, n)
        self.node.rois.append(new)
        self.endInsertRows()
        self.changed.emit()
        return n

    def delete_item(self, n):
        if n < len(self.node.rois):
            self.beginRemoveRows(QModelIndex(), n, n)
            del self.node.rois[n]
            self.endRemoveRows()
            self.changed.emit()


def setColourButton(but, col):
    r, g, b = [x * 255 for x in col]
    but.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b))


class TabROIExpr(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabroiexpr.ui')
        self.w.addButton.clicked.connect(self.addClicked)
        self.w.dupButton.clicked.connect(self.dupClicked)
        self.w.deleteButton.clicked.connect(self.deleteClicked)
        self.w.tableView.delete.connect(self.deleteClicked)
        self.w.tableView.selChanged.connect(self.selectionChanged)
        self.w.exprEdit.editingFinished.connect(self.exprChanged)
        self.w.hideCheck.stateChanged.connect(self.hideCheckChanged)
        self.w.outColButton.clicked.connect(self.outColButtonChanged)
        self.w.selColButton.clicked.connect(self.selColButtonChanged)
        self.w.unselColButton.clicked.connect(self.unselColButtonChanged)
        self.w.brushSize.valueChanged.connect(self.brushSizeChanged)
        self.w.tableView.doubleClicked.connect(self.doubleClick)

        self.model = Model(self, node)
        self.w.tableView.setModel(self.model)
        self.w.tableView.horizontalHeader().setStretchLastSection(True)
        self.model.changed.connect(self.roisChanged)
        self.w.canvas.mouseHook = self
        self.w.canvas.paintHook = self
        self.nodeChanged()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.img)
        self.w.tableView.dataChanged(QModelIndex(), QModelIndex())

        self.w.exprEdit.setText(self.node.expr)
        self.w.hideCheck.setChecked(self.node.hideROIs)
        self.w.brushSize.setValue(self.node.brushSize)
        setColourButton(self.w.outColButton, self.node.outColour)
        setColourButton(self.w.selColButton, self.node.selColour)
        setColourButton(self.w.unselColButton, self.node.unselColour)

    def doubleClick(self, index):
        item = index.row()
        # we need to tell the dialog the size of the image we are working with so it can set limits
        # in the editor dialogs.
        w = 2000    # defaults
        h = 2000
        if self.node.img is not None:
            w = self.node.img.w
            h = self.node.img.h

        if 0 <= item < len(self.node.rois):
            item = self.node.rois[item]
            self.node.editors[item].openDialog(w, h)

    def brushSizeChanged(self, val):
        self.mark()
        self.node.brushSize = val
        self.changed()

    def outColButtonChanged(self):
        col = pcot.utils.colour.colDialog(self.node.outColour)
        if col is not None:
            self.mark()
            self.node.outColour = col
            self.changed()

    def selColButtonChanged(self):
        col = pcot.utils.colour.colDialog(self.node.selColour)
        if col is not None:
            self.mark()
            self.node.selColour = col
            self.changed()

    def unselColButtonChanged(self):
        col = pcot.utils.colour.colDialog(self.node.unselColour)
        if col is not None:
            self.mark()
            self.node.unselColour = col
            self.changed()

    def exprChanged(self):
        self.mark()
        self.node.expr = self.w.exprEdit.text()
        self.changed()

    def hideCheckChanged(self, t):
        self.node.hideROIs = t != 0
        self.changed()

    def selectionChanged(self, idx):
        self.node.selected = idx
        self.changed(uiOnly=True)

    def roisChanged(self):
        pass

    def get_selected_item(self):
        sel = self.w.tableView.selectionModel()
        if sel.hasSelection():
            if len(sel.selectedRows()) > 0:
                return sel.selectedRows()[0].row()
        return None

    def selectItem(self, item):
        self.w.tableView.selectColumn(item)

    def addClicked(self):
        item = self.model.add_item()
        self.w.tableView.selectItem(item)

    def dupClicked(self):
        if (item := self.get_selected_item()) is not None:
            item = self.model.add_item(item)
            self.w.tableView.selectItem(item)

    def deleteClicked(self):
        if (item := self.get_selected_item()) is not None:
            if QMessageBox.question(None, "Delete item", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.model.delete_item(item)

    def getEditor(self):
        if (item := self.get_selected_item()) is not None:
            roi = self.node.rois[item]
            return self.node.editors[roi]
        return None

    def canvasPaintHook(self, p: QPainter):
        if (editor := self.getEditor()) is not None:
            editor.canvasPaintHook(p)

    def canvasMouseMoveEvent(self, x, y, e):
        if (editor := self.getEditor()) is not None:
            editor.canvasMouseMoveEvent(x, y, e)

    def canvasMousePressEvent(self, x, y, e):
        if (editor := self.getEditor()) is not None:
            editor.canvasMousePressEvent(x, y, e)

    def canvasMouseReleaseEvent(self, x, y, e):
        if (editor := self.getEditor()) is not None:
            editor.canvasMouseReleaseEvent(x, y, e)
