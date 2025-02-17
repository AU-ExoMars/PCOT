import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Optional, List

from PySide2 import QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtGui import QPen
from PySide2.QtWidgets import QMessageBox, QTableWidgetItem
from proctools.products import ProductDepot, DataProduct

import pcot
import pcot.dq
import pcot.ui as ui
from pcot.dataformats.pds4 import PDS4ImageProduct, ProductList
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping
from pcot.inputs.inputmethod import InputMethod
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui import uiloader
from pcot.ui.canvas import Canvas
from pcot.ui.help import HelpWindow
from pcot.ui.inputs import MethodWidget
from pcot.ui.linear import LinearSetEntity, entityMarkerInitSetup, entityMarkerPaintSetup, TickRenderer

logger = logging.getLogger(__name__)

PRIVATEDATAROLE = 1000  # data role for table items

helpText = """# PDS4 Input

* Select a directory which contains PDS4 products by clicking on the "Browse" button.
* Set 'recursive directory scan' appropriately. Be careful - you could end up reading a huge number of products!
* Click "Scan Directory" to read in the products - the table and timeline will now be populated.
* Select those products who data you wish to use, in either the table or timeline. If more than one
product is selected, they must all be images.
* Click "Read" to actually read the product data so that they can be read from the "input" nodes in the graph.
     
"""


def timestr(t):
    return t.strftime("%x %X")


# list of multiplication factors - sets the combo in the UI
MULTVALUES = [1, 1024, 2048]


class PDS4InputMethod(InputMethod):
    """PDS4 inputs are unusual in that they can come from several PDS4 products, not a single file.
    We load them into a ProductList object."""

    # Here is the data model. This all gets persisted.

    products: Optional[ProductList]  # list of PDS4 products found under the directory "dir". Not all will be selected.
    selected: List[int]  # indices of selected items in the above list

    dir: Optional[str]  # the directory we have got the data from; just used to set up the widget
    mapping: ChannelMapping  # the mapping for the canvas
    recurse: bool  # when scanning directories, should we do it recursively?
    multValue: float  # multiplication to apply post-load

    def __init__(self, inp):
        super().__init__(inp)
        self.out = None
        self.products = None
        self.selected = []
        self.dir = None
        self.mapping = ChannelMapping()
        self.recurse = False
        self.multValue = 1.0

    def loadLabelsFromDirectory(self, clear=False):
        """This will actually load data from the directory"""

        # TODO - clear is unused!

        logger.debug("loadLabelsFromDirectory")
        if self.dir is not None:
            # Exceptions might get thrown; the caller must handle them.
            depot = ProductDepot()
            # this is actually loading 'labels' in *my* terminology
            logger.debug("Loading products...")

            for x in Path(self.dir).expanduser().rglob("*.xml"):
                print(x)

            depot.load(Path(self.dir), recursive=self.recurse)
            logger.debug("...products loaded")
            # Retrieve labels for all loaded PAN-PP-220/spec-rad products as instances of
            # proctools.products.pancam:SpecRad; sub in the mnemonic of the product you're after

            # OLD way of doing it, might still be useful - concatenate a bunch of calls to retrieve for each product
            # type we are interested in.

            # products = depot.retrieve("spec-rad")

            # NEW way of doing it, just retrieve everything and deal with the fact that we get a defaultdict back.
            products = []
            pdict = depot.retrieve(None)
            for k, v in pdict.items():
                if isinstance(v, list):
                    products.extend(v)

            # generate a list of PDS4Product objects
            self.products = ProductList(products)
            pcot.config.setDefaultDir('images', self.dir)
            pcot.config.save()

    def setProducts(self, products: List[DataProduct]) -> InputMethod:
        """Used from the document's setInputPDS4() method when we're using PCOT as a library and loaded
        a bunch of DataProducts from code"""
        self.selected = [i for i, _ in enumerate(products)]
        self.products = ProductList(products)
        return self

    def loadData(self):
        """Actually load the data; or rather load the actual data from my PDS4.. objects and the proctools DataProduct
        "label" objects. The magic now happens inside the ProductList.toDatum() method."""

        self.out = self.products.toDatum(multValue=self.multValue, mapping=self.mapping,
                                         selection=self.selected,
                                         inpidx=self.input.idx)

        # if we didn't get any data, set the output to null
        if self.out is None:
            self.out = Datum.null

        # finally rerun the document's graph
        self.input.performGraph()

    def readData(self) -> Datum:
        logger.debug("readData")
        self.loadData()
        return self.out

    def getName(self):
        return "PDS4"

    def createWidget(self):
        return PDS4ImageMethodWidget(self)

    def serialise(self, internal):
        # serialise the parameters
        x = {'recurse': self.recurse,
             'mult': self.multValue,
             'selected': self.selected,
             'products': self.products.serialise() if self.products is not None else None,
             'dir': self.dir,
             'mapping': self.mapping.serialise()}
        if internal:
            x['out'] = self.out
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        try:
            self.multValue = data.get('mult', 1)
            self.recurse = data['recurse']
            self.selected = data['selected']
            self.products = ProductList.deserialise(data['products']) if data['products'] is not None else None
            self.dir = data['dir']
            self.mapping = ChannelMapping.deserialise(data['mapping'])
            if internal:
                self.out = data['out']
            else:
                self.out = None  # ensure image is reloaded
            Canvas.deserialise(self, data)
        except KeyError as e:
            ui.error(f"can't read '{e}' from serialised PDS4 input data")

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        m = d.pds4
        if m.directory is None:
            return False  # no change to this input (directory must be provided)

        self._getFilesFromParameterDict(m)

        plist = [DataProduct.from_file(Path(os.path.join(self.dir, f))) for f in self.files]
        self.setProducts(plist)
        return True

class ImageMarkerItem(QtWidgets.QGraphicsRectItem):
    """Marker for images"""

    def __init__(self, x, y, ent, isLeft, radius=5):
        super().__init__(x - radius, y - radius, radius * 2, radius * 2)
        r2 = radius / 2  # radius of internal circle
        xoffset = -r2 if isLeft else r2
        sub = QtWidgets.QGraphicsEllipseItem(x + xoffset - radius / 2, y - r2, r2 * 2, r2 * 2, parent=self)
        sub.setPen(QPen(Qt.NoPen))
        sub.setBrush(Qt.black)
        entityMarkerInitSetup(self, ent)
        self.unselCol = Qt.cyan

    def paint(self, painter, option, widget):
        """and draw."""
        entityMarkerPaintSetup(self, option, self.unselCol, self.selCol)
        super().paint(painter, option, widget)


class ImageLinearSetEntity(LinearSetEntity):
    """This is an entity which uses the above marker item"""

    def createMarkerItem(self, x, y):
        """Create a marker item to display - this inspects the underlying product, ensures it's an image
        and looks at the camera field to see whether it's from the left or right camera. We could do other
        things here too (different icons for geology, colour etc.)"""
        isLeft = isinstance(self.data, PDS4ImageProduct) and self.data.camera == 'WACL'
        return ImageMarkerItem(x, y, self, isLeft)


class PDS4ImageMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi('inputpdsfile.ui', self)

        # set widget states from method data
        if self.method.dir is None or not os.path.isdir(self.method.dir):
            # if the method hasn't set up the directory yet, or that directory doesn't exist, use the default/
            d = pcot.config.getDefaultDir('images')
            d = '.' if d is None or d == '' else d
            self.method.dir = d
        self.fileEdit.setText(self.method.dir)

        self.recurseBox.setCheckState(Qt.Checked if self.method.recurse else Qt.Unchecked)

        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        # prescan the directory?? Not now; any data will
        # be serialised in the method object - we only do
        # this when we want to get new data.

        # self.method.loadLabelsFromDirectory()

        # initialise combo
        self.multCombo.clear()
        for x in MULTVALUES:
            self.multCombo.addItem(f"x{x}", userData=x)

        # connect signals

        self.recurseBox.stateChanged.connect(self.recurseChanged)
        self.browse.clicked.connect(self.browseClicked)
        self.scanDirButton.clicked.connect(self.scanDirClicked)
        self.readButton.clicked.connect(self.readClicked)
        self.table.itemSelectionChanged.connect(self.tableSelectionChanged)
        self.timeline.selChanged.connect(self.timelineSelectionChanged)
        self.multCombo.currentIndexChanged.connect(self.multChanged)
        self.helpButton.clicked.connect(self.helpClicked)

        # if we are updating the selected items this should be true so that we don't end up recursing.
        self.selectingItems = False

        # set up the timeline and table

        self.initTimeline()
        self.initTable()
        self.populateTableAndTimeline()
        self.showSelectedItems()
        self.updateDisplay()

    def getProducts(self):
        """get the list of products from the method's ProductList.
        If there are none, return an empty list."""
        return self.method.products.lst if self.method.products is not None else []

    def initTable(self):
        """initialise the table of PDS4 products"""
        cols = ["sol", "start", "PTU", "camera", "filter", "cwl"]
        t = self.table
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)

    def addTableRow(self, strs, data):
        self.table.insertRow(self.table.rowCount())
        n = self.table.rowCount() - 1
        for i, x in enumerate(strs):
            w = QTableWidgetItem(x)
            w.setData(PRIVATEDATAROLE, data)
            self.table.setItem(n, i, w)

    def initTimeline(self):
        """initialise the PDS4 product timeline"""
        # create some tick renderers for the widget
        # this is for big text when the ticks are far apart
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=20, textcol=(0, 0, 255), minxdist=50,
                                                   textoffset=-10,
                                                   textgenfunc=lambda x: f"sol {int(x)}"))
        # this is the same, but the text is smaller and renders when the ticks are close together
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=10, textcol=(0, 0, 255), maxxdist=50,
                                                   textgenfunc=lambda x: f"{int(x)}"))

        # and these are intermediate values
        self.timeline.addTickRenderer(
            TickRenderer(spacing=0.1, fontsize=8, textoffset=10, linecol=(230, 230, 230), linelen=0.5, minxdist=10,
                         textgenfunc=lambda x: f"{int(x * 10 + 0.3) % 10}", textalways=True))
        self.timeline.setYOffset(40)  # make room for axis text

    def populateTableAndTimeline(self):
        """Refresh the table and timeline to reflect what's stored in the method."""
        # first the table.
        self.table.clearContents()  # this will just make all the data empty strings (or null widgets)
        self.table.setRowCount(0)  # and this will remove the rows

        # get the products and add them to the table

        products = self.getProducts()
        for p in products:
            strs = [
                str(p.sol_id),
                timestr(p.start),
                str(p.rmc_ptu),
                p.camera,
                p.filt.name,
                str(p.filt.cwl)
            ]
            self.addTableRow(strs, p)
        self.table.resizeColumnsToContents()

        # now the timeline

        items = []
        xspacing = dict()  # this is used so that points with filter and sol the same have different X (slightly)
        for p in products:
            key = (p.idx, p.sol_id)
            if key in xspacing:
                xspac = xspacing[key] + 0.1
            else:
                xspac = 0
            xspacing[key] = xspac

            yOffset = p.idx * 12
            items.append(ImageLinearSetEntity(p.sol_id + xspac, yOffset, f"{p.filt.cwl} ({p.filt.name})", p))
        self.timeline.setItems(items)
        self.timeline.rescale()
        self.timeline.rebuild()

    def showSelectedItems(self, timelineOnly=False, tableOnly=False):
        """Update the timeline and table to show the items selected in the method. The xxxOnly booleans
        are there to make sure we don't inadvertently mess up the widget we have just selected
        items in (although it really shouldn't matter)."""

        # generate list of PDS4Product objects
        products = self.getProducts()
        selitems = [products[i] for i in self.method.selected]
        self.selectingItems = True

        # now the timeline. Yeah, the model is pretty ugly here for selection in the timeline, specifying
        # the actual LinearSetEntities that are selected.
        if not tableOnly:
            sel = []
            for x in self.timeline.items:
                if x.data in selitems:
                    sel.append(x)
            self.timeline.setSelection(sel)

        # now, the table.

        if not timelineOnly:
            self.table.clearSelection()
            for i in range(0, self.table.rowCount()):
                itemInTable = self.table.item(i, 0)  # get the first item in the column
                # and get that item's private data, which will be the PDS4Product object (as it will for all columns)
                if itemInTable is not None and itemInTable.data(PRIVATEDATAROLE) in selitems:
                    self.table.selectRow(i)
        self.selectingItems = False

    def tableSelectionChanged(self):
        if not self.selectingItems:
            # this gets the data items - the actual PDS4 product objects - selected in the table
            items = [x.data(PRIVATEDATAROLE) for x in self.table.selectedItems()]
            sel = []
            for i, x in enumerate(self.getProducts()):
                if x in items:
                    sel.append(i)
            self.method.selected = sel
            self.showSelectedItems(timelineOnly=True)

    def timelineSelectionChanged(self):
        """timeline selection changed, we need to make the table sync up"""
        if not self.selectingItems:
            items = [x.data for x in self.timeline.getSelection()]
            # print(self.timeline.getSelection())
            # print([x.filt.name for x in items])
            sel = []
            for i, x in enumerate(self.getProducts()):
                if x in items:
                    sel.append(i)
            self.method.selected = sel
            self.showSelectedItems(tableOnly=True)

    def cameraChanged(self, i):
        self.method.camera = "PANCAM" if i == 0 else "AUPE"
        # not really necessary here because it only affects what happens when we scan
        self.onInputChanged()

    def multChanged(self, i):
        self.method.multValue = self.multCombo.currentData()
        self.readClicked()
        self.onInputChanged()

    def recurseChanged(self, v):
        """recursion checkbox toggled"""
        self.method.recurse = (v != 0)

    def scanDir(self):
        """Scan the selected directory for PDS4 products and populate the model, refreshing the timeline and table"""
        try:
            self.method.loadLabelsFromDirectory(clear=False)
            self.populateTableAndTimeline()
            self.onInputChanged()
        except Exception as e:
            logger.exception("Error scanning directory", exc_info=e)
            estr = pcot.utils.deb.simpleExceptFormat(e)
            QMessageBox.critical(self, 'Error', estr)
            ui.log(estr)

    def scanDirClicked(self):
        """Does a scanDir() if we confirm it"""
        if QMessageBox.question(None, "Rescan directory",
                                "This will clear all loaded products. Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.scanDir()

    def readClicked(self):
        """Read selected data, checking for validity, and generate output"""
        try:
            self.method.loadData()
            self.onInputChanged()
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            ui.log(str(e))

    def browseClicked(self):
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for products',
                                                         os.path.expanduser(self.method.dir),
                                                         options=pcot.config.getFileDialogOptions())
        if res != '':
            self.fileEdit.setText(res)
            self.method.dir = res

    def helpClicked(self):
        HelpWindow(self, md=helpText, node=self)

    def updateDisplay(self):
        """Change the display to show the 'out' of the method."""
        if self.method.out is not None:
            img = self.method.out.get(Datum.IMG)
            self.canvas.display(img)

    def onInputChanged(self):
        # ensure image is also using my mapping.
        if self.method.out is not None and self.method.out.tp == Datum.IMG:
            self.method.out.val.setMapping(self.method.mapping)

        idx = self.multCombo.findData(self.method.multValue)
        if idx >= 0:
            self.multCombo.setCurrentIndex(idx)
        else:
            logger.error(
                f"setting multiplier combo index to 0, because I don't know about multiplier {self.method.multValue}!")

        logger.debug("Displaying data {}, mapping {}".format(self.method.out, self.method.mapping))
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.updateDisplay()
