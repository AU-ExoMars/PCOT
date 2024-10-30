"""This node manages several ROIs, allows editing, and combines them with an expression. Much more convenient
than using multiple ROI and expr nodes with an importroi node."""
from copy import copy
from functools import partial

from PySide2.QtCore import QModelIndex, Signal, QAbstractTableModel, Qt
from PySide2.QtGui import QPainter
from PySide2.QtWidgets import QInputDialog, QMessageBox

from pcot.rois import ROICircle, ROIPainted, ROIPoly, ROIRect, ROI
import pcot.ui
from pcot import ui
from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.imagecube import ImageCube
from pcot.sources import nullSourceSet
from pcot.ui.tabs import Tab
from pcot.parameters.taggedaggregates import TaggedVariantDictType, TaggedListType, TaggedDictType, TaggedDict
from pcot.xform import xformtype, XFormType, XFormException


def getROIName(i):
    """Get the name of an ROI from its index. If it's greater than 26, return a string name."""
    return chr(97 + i) if i < 26 else f"roi{i}"


@xformtype
class XFormROIExpr(XFormType):
    """
    This node allows a region of interest to be composed from several regions of interest using an expression and
    imposed on an image.

    **It is not a node for creating several ROIs at once - the output is always a single ROI**.

    ROIs can be created for use within the expression by using the "Add ROI" button.
    These will be assigned to the variables a,b,c.. within the expression, and can be edited by:

    * clicking on their label in the left-most column of the table (to select the entire row) and then clicking and dragging on the canvas,
    * double clicking on the description text in the table to open a numerical editor (not for poly or painted).

    Additional ROIs can be connected to the p, q, r inputs; these will be assigned to those variables within the expression.
    The input image's ROIs are combined into a single ROI and assigned to the variable 'i'.
    The input image itself is available as the variable 'img'.

    Other properties of the image are available and other calculations may be made, but the result of the expression must be an ROI.

    Examples:

    * **a+b** : the union of ROIs 'a' and 'b' from the node's ROI list
    * **a*b** : the intersection of ROIs 'a' and 'b'
    * **a-b** : ROI 'a' with ROI 'b' removed
    * **-a** :   the negative of ROI 'a' (i.e. the entire image area as an ROI but with a hole in it)
    * **roi(img) - p**  : any ROIs on the image already, but with the ROI on input 'p' cut out

    """

    TAGGEDVDICT = TaggedVariantDictType("type",
                                        {
                                            "painted": ROIPainted.TAGGEDDICT,
                                            "circle": ROICircle.TAGGEDDICT,
                                            "poly": ROIPoly.TAGGEDDICT,
                                            "rect": ROIRect.TAGGEDDICT
                                        })

    TAGGEDLIST = TaggedListType("", TAGGEDVDICT, 0)

    def __init__(self):
        super().__init__("roiexpr", "regions", "0.0.0")
        self.addInputConnector("", Datum.IMG, "Image input")
        self.addInputConnector("p", Datum.ROI, "ROI which appears as 'p' in expression")
        self.addInputConnector("q", Datum.ROI, "ROI which appears as 'q' in expression")
        self.addInputConnector("r", Datum.ROI, "ROI which appears as 'r' in expression")
        self.addOutputConnector("", Datum.IMG, "Output image with ROI from expression result imposed")
        self.addOutputConnector("", Datum.ROI, "The ROI generated from the expression")

        # quite a lot of parameters still use the old system, which can't be modified by parameter files.
        self.autoserialise = ('selColour', 'unselColour', 'outColour', 'hideROIs', 'previewRadius',
                              ('imgROIColour', (1, 0, 1)))

        self.params = TaggedDictType(rois=("List of ROIs", self.TAGGEDLIST),
                                     expr=("Expression", str, ""))

    def createTab(self, n, w):
        return TabROIExpr(n, w)

    def init(self, node):
        node.rois = []
        node.canvimg = None
        node.selColour = (0, 1, 0)  # colour of selected ROI
        node.unselColour = (0, 1, 1)  # colour of unselected ROI
        node.outColour = (1, 1, 0)  # colour of output ROI
        node.imgROIColour = (1, 0, 1)  # colour of input image's ROI

        node.hideROIs = False  # hide individual ROIs
        node.brushSize = 20  # scale of 0-99 i.e. a slider value. Converted to pixel radius in getRadiusFromSlider()
        node.previewRadius = None  # see xformpainted.

        # create the parameter TaggedDict structure we'll be working with
        node.params = TaggedDict(self.params)

    def serialise(self, node):
        # create the list of ROI data
        lst = self.TAGGEDLIST.create()
        for r in node.rois:
            # for each ROI, convert to a TaggedDict
            d = r.to_tagged_dict()
            # wrap it in a TaggedVariantDict and store it in the list
            dv = self.TAGGEDVDICT.create().set(d)
            lst.append(dv)

        # store the ROIs in the params
        node.params.rois = lst
        # and don't return anything, because we've stored the data in node.params.
        return None

    def nodeDataFromParams(self, node):
        # here, we do extra work to retrieve parameters from the .params structure.
        # for more detail, see how multidot's deserialise does it!
        node.rois = [ROI.new_from_tagged_dict(x.get()) for x in node.params.rois]

    def perform(self, node):
        img: ImageCube = node.getInput(0, Datum.IMG)

        #
        # All this code assumes that there are no sources in the ROIs it uses.
        #

        node.roi = None
        outROIDatum = Datum.null

        # this colour is used for painted node preview.
        node.colour = node.selColour

        # must be an image, and must be an expression
        if img is not None:
            img = img.copy()
            node.previewRadius = pcot.rois.getRadiusFromSlider(node.brushSize, img.w, img.h)

            # update the ROIs so that the image dimensions are correct
            for r in node.rois:
                # patch image size into the ROI so we can do negation
                r.setContainingImageDimensions(img.w, img.h)

            # we create a new parser here, because we want it to be empty of ROIs etc.
            parser = ExpressionEvaluator()
            for i, r in enumerate(node.rois):
                r.drawBox = False
                # register the ROIs into the parser (or rather lambdas that return datums)
                roiname = getROIName(i)
                # Register a variable which returns an ROI datum for that ROI
                # *shakes fist at late-binding closures*
                f = partial(lambda ii: Datum(Datum.ROI, node.rois[ii], sources=nullSourceSet), i)
                parser.registerVar(roiname, f'value of ROI {i}', f)
            # might be useful to have the input image there too
            parser.registerVar('img', 'input image', lambda: Datum(Datum.IMG, img))
            # and three extra ROI inputs that might come from other data

            # get any ROIs on the image and union them
            if len(img.rois) > 0:
                # register the union of these ROIs as 'i'
                imgroi = pcot.rois.ROI.roiUnion(img.rois)
                imgroi.colour = node.imgROIColour
                if imgroi is not None:
                    imgroi = Datum(Datum.ROI, imgroi, imgroi.getSources())
                else:
                    imgroi = Datum.null
            else:
                imgroi = Datum.null
            parser.registerVar('i', 'union of image ROIs', lambda: imgroi)

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

            inROIp = getROIInput(1)
            inROIq = getROIInput(2)
            inROIr = getROIInput(3)
            inROIlist = [x for x in [inROIp, inROIq, inROIr, imgroi] if x is not None]

            parser.registerVar("p", "ROI input p", lambda: inROIp)
            parser.registerVar("q", "ROI input q", lambda: inROIq)
            parser.registerVar("r", "ROI input r", lambda: inROIr)

            if len(node.params.expr.strip()) > 0:
                # now execute the expression and get it back as an ROI
                res = parser.run(node.params.expr)
                node.roi = res.get(Datum.ROI)
                node.roi.drawBox = False
                # set its colour
                if node.roi is not None:
                    node.roi.drawBox = False
                    node.roi.colour = node.outColour
                    # impose that ROI on the image - REMOVING existing ROIs
                    img.rois = [node.roi]
                    outROIDatum = Datum(Datum.ROI, node.roi, node.roi.sources)
            else:
                img.rois = []  # remove all existing ROIs from the image for output
            # impose the individual ROIs as annotations
            if not node.hideROIs:
                # we want to see the input ROIs as well, so add them.
                inROIlist = [x.get(Datum.ROI) for x in inROIlist]
                img.annotations = node.rois + [x for x in inROIlist if x is not None]
                ui.log(f"Adding {len(img.annotations)} ROIs to annotations")
            else:
                ui.log("Not adding ROIs to annotations")
                img.annotations = []
            # set mapping from node
            img.setMapping(node.mapping)
            # 'img' so far is the image we are going to display.
            node.canvimg = img
            # but the image we are going to output is going to be different - it will have no annotations
            # because we don't want to see the sub-ROIs in the descendants.
            img = img.shallowCopy(copyAnnotations=False)

        outImgDatum = Datum(Datum.IMG, img)
        node.setOutput(0, outImgDatum)
        node.setOutput(1, outROIDatum)

    def clearData(self, xform):
        xform.canvimg = None

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
        self.editors = dict()  # keyed on index in list

        # create editors for existing nodes
        for i, r in enumerate(self.tab.node.rois):
            self.editors[i] = r.createEditor(tab)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLNAMES[section]
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return getROIName(section)  # index number to a,b,c,d...
        return super().headerData(section, orientation, role)

    def rowCount(self, index):
        return len(self.tab.node.rois)

    def columnCount(self, index):
        return len(COLNAMES)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            item = index.row()
            field = index.column()
            roi = self.tab.node.rois[item]

            if field == 0:
                return roi.tpname
            elif field == 1:
                return str(roi)

    def add_item(self, sourceIndex=None):
        node = self.tab.node
        n = len(node.rois)
        if sourceIndex is None:
            # pick an ROI - this is a dict of name to class
            choices = {x.tpname: x for x in pcot.rois.ROI.__subclasses__()}
            k, ok = QInputDialog.getItem(None, "Select a type", "type", list(choices.keys()), 0, False)
            if not ok:
                return
            # construct the new item - we'll set the dimensions in perform too.
            new = choices[k]()
            img = node.getInput(0, Datum.IMG)
            if img is not None:  # not much we can do if there's no image -
                # but that can't happen, how would we click on it?
                new.setContainingImageDimensions(img.w, img.h)
        else:
            new = node.rois[sourceIndex].copy()
        new.colour = (0, 1, 0)  # green by default
        # create an editor for the new ROI
        self.editors[n] = new.createEditor(self.tab)
        self.beginInsertRows(QModelIndex(), n, n)
        node.rois.append(new)
        self.endInsertRows()
        self.changed.emit()
        return n

    def delete_item(self, n):
        if n < len(self.tab.node.rois):
            self.beginRemoveRows(QModelIndex(), n, n)
            del self.tab.node.rois[n]
            del self.editors[n]
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
        self.w.imgROIColButton.clicked.connect(self.imgROIColButtonChanged)
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
        node = self.node
        # here we apply colour to the selected ROI. We used to do this in perform.
        # but this data got lost after an undo. It's not a good idea to keep the
        # selected index in the node.
        selected = self.get_selected_item()
        for i, r in enumerate(node.rois):
            r.colour = node.selColour if i == selected else node.unselColour

        self.w.canvas.setNode(self.node)
        self.w.canvas.setROINode(node)
        self.w.canvas.display(node.canvimg)
        self.w.tableView.dataChanged(QModelIndex(), QModelIndex())

        self.w.exprEdit.setText(node.params.expr)
        self.w.hideCheck.setChecked(node.hideROIs)
        self.w.brushSize.setValue(node.brushSize)
        setColourButton(self.w.outColButton, node.outColour)
        setColourButton(self.w.selColButton, node.selColour)
        setColourButton(self.w.unselColButton, node.unselColour)
        setColourButton(self.w.imgROIColButton, node.imgROIColour)

    def doubleClick(self, index):
        item = index.row()
        # we need to tell the dialog the size of the image we are working with so it can set limits
        # in the editor dialogs.
        w = 2000  # defaults
        h = 2000
        if self.node.canvimg is not None:
            w = self.node.canvimg.w
            h = self.node.canvimg.h

        if 0 <= item < len(self.node.rois):
            self.model.editors[item].openDialog(w, h)

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

    def imgROIColButtonChanged(self):
        col = pcot.utils.colour.colDialog(self.node.imgROIColour)
        if col is not None:
            self.mark()
            self.node.imgROIColour = col
            self.changed()

    def exprChanged(self):
        self.mark()
        self.node.params.expr = self.w.exprEdit.text()
        self.changed()

    def hideCheckChanged(self, t):
        self.node.hideROIs = t != 0
        self.changed()

    def selectionChanged(self, idx):
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
            try:
                return self.model.editors[item]
            except KeyError:
                ui.log(f"Can't open editor for ROI {item}")
        return None

    def getROI(self):
        if (item := self.get_selected_item()) is not None:
            try:
                return self.node.rois[item]
            except IndexError:
                ui.log(f"Can't get ROI {item}")
        raise XFormException('INTR', "No ROI selected in getROI()")

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
