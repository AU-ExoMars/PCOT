import os
import traceback
from pathlib import Path
from typing import Optional, List

from dateutil import parser
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem

from pcot import filters
from proctools.products.loader import ProductLoader

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.ui.linear import LinearSetEntity, entityMarkerInitSetup, entityMarkerPaintSetup, TickRenderer
from pcot.dataformats.pds4 import PDS4Product, PDS4ImageProduct

PRIVATEDATAROLE = 1000  # data role for table items


def timestr(t):
    return t.strftime("%x %X")


class PDS4ImageInputMethod(InputMethod):
    """PDS4 inputs are unusual in that they can come from several PDS4 products, not a single file."""

    # Here is the data model. This all gets persisted.

    img: Optional[ImageCube]  # the output - just image supported for now.

    products: List[PDS4ImageProduct]  # list of PDS4 products found under the directory "dir". Not all will be selected.
    selected: List[int]  # indices of selected items in the above list

    dir: Optional[str]  # the directory we have got the data from; just used to set up the widget
    mapping: ChannelMapping  # the mapping for the canvas
    recurse: bool  # when scanning directories, should we do it recursively?
    camera: str  # type of camera - 'PANCAM' or 'AUPE'

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.products = []
        self.selected = []
        self.dir = None
        self.mapping = ChannelMapping()
        self.recurse = False
        self.camera = 'PANCAM'

    def loadLabelsFromDirectory(self):
        """This will actually load data from the directory into the linear widget. """
        if self.dir is not None:
            self.products = []
            self.selected = []

            # Exceptions might get thrown; the caller must handle them.
            loader = ProductLoader()
            loader.load_products(Path(self.dir), recursive=self.recurse)
            # Retrieve all loaded PAN-PP-220/spec-rad products as instances of
            # proctools.products.pancam:SpecRad; sub in the mnemonic of the product you're after
            for dat in loader.all("spec-rad"):
                m = dat.meta
                start = parser.isoparse(m.start)
                cwl = int(m.filter_cwl)
                sol = int(m.sol_id)
                seq = int(m.seq_num)
                ptu = float(m.rmc_ptu)

                # try to work out what filter we are. This is a complete pig - we might
                # be AUPE, we might be PANCAM. We have to rely on document settings.
                filt = filters.findFilter(self.camera, m.filter_id)
                if filt.cwl != cwl:
                    raise Exception(
                        f"Filter CWL does not match for filter {m.filter_id}: file says {cwl}, should be {filt.cwl}")
                prod = PDS4ImageProduct(sol, seq, filt, m.camera, ptu, start)
                self.products.append(prod)
            self.products.sort(key=lambda p: p.start)
            pcot.config.setDefaultDir('images', self.dir)

    def loadImg(self):
        print("PDS4IMAGE PERFORMING FILE READ")
        img = None
        #        ui.log("Image {} loaded: {}, mapping is {}".format(self.fname, img, self.mapping))
        self.img = img

    def readData(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "PDS4"

    def set(self, *args):
        """used from external code"""
        raise NotImplementedError  # TODO
        self.mapping = ChannelMapping()

    def createWidget(self):
        return PDS4ImageMethodWidget(self)

    def serialise(self, internal):
        x = {'recurse': self.recurse,
             'selected': self.selected,
             'products': [x.serialise() for x in self.products],
             'dir': self.dir,
             'camera': self.camera,
             'mapping': self.mapping.serialise()}
        if internal:
            x['image'] = self.img
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        if 'recurse' in data:
            self.recurse = data['recurse']
            self.selected = data['selected']
            self.camera = data['camera']
            self.products = [PDS4Product.deserialise(x) for x in data['products']]
            self.dir = data['dir']
            self.mapping = ChannelMapping.deserialise(data['mapping'])
            if internal:
                self.img = data['image']
            else:
                self.img = None  # ensure image is reloaded
            Canvas.deserialise(self, data)

    def long(self):
        # TODO ??
        return f"PDS4-{self.input.idx}"


class ExampleMarkerItem(QtWidgets.QGraphicsRectItem):
    """This is an example marker item which is a cyan rectangle - other than that it's the
    same as the standard kind."""

    def __init__(self, x, y, ent, radius=10):
        super().__init__(x - radius / 2, y - radius / 2, radius, radius)
        entityMarkerInitSetup(self, ent)
        self.unselCol = Qt.cyan

    def paint(self, painter, option, widget):
        """and draw."""
        entityMarkerPaintSetup(self, option, self.unselCol, self.selCol)
        super().paint(painter, option, widget)


class ExampleLinearSetEntityA(LinearSetEntity):
    """This is an entity which uses the above example marker item"""

    def createMarkerItem(self, x, y):
        return ExampleMarkerItem(x, y, self)


class PDS4ImageMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uic.loadUi(pcot.config.getAssetAsFile('inputpdsfile.ui'), self)

        # set widget states from method data
        if self.method.dir is None or not os.path.isdir(self.method.dir):
            # if the method hasn't set up the directory yet, or that directory doesn't exist, use the default/
            d = pcot.config.getDefaultDir('images')
            d = '.' if d is None or d == '' else d
            self.method.dir = d
        self.fileEdit.setText(self.method.dir)

        self.recurseBox.setCheckState(2 if self.method.recurse else 0)

        self.canvas.setMapping(m.mapping)
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        # prescan the directory?? Not now; any data will
        # be serialised in the method object - we only do
        # this when we want to get new data.

        # self.method.loadLabelsFromDirectory()

        # connect signals

        self.recurseBox.stateChanged.connect(self.recurseChanged)
        self.browse.clicked.connect(self.browseClicked)
        self.scanDirButton.clicked.connect(self.scanDirClicked)
        self.readButton.clicked.connect(self.readClicked)
        self.camCombo.currentIndexChanged.connect(self.cameraChanged)
        self.table.itemSelectionChanged.connect(self.tableSelectionChanged)
        self.timeline.selChanged.connect(self.timelineSelectionChanged)

        # if we are updating the selected items this should be true so that we don't end up recursing.
        self.selectingItems = False

        # set up the timeline and table

        self.initTimeline()
        self.initTable()

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
        for p in self.method.products:
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

        # then the timeline

        items = []
        for p in self.method.products:
            yOffset = p.filt.idx * 12
            items.append(LinearSetEntity(p.sol_id, yOffset, p.filt.name, p))
        self.timeline.setItems(items)
        self.timeline.rescale()
        self.timeline.rebuild()

    def showSelectedItems(self):
        """Update the timeline and table to show the items selected in the method"""

        selitems = [self.method.products[i] for i in self.method.selected]
        self.selectingItems = True

        # now the timeline. Yeah, the model is pretty ugly here for selection in the timeline, specifying
        # the actual LinearSetEntities that are selected.
        sel = []
        for x in self.timeline.items:
            if x.data in selitems:
                sel.append(x)
        self.timeline.setSelection(sel)

        # now, the table.

        for i in range(0, self.table.rowCount()):
            itemInTable = self.table.item(i, PRIVATEDATAROLE)
            if itemInTable is not None and itemInTable.data(PRIVATEDATAROLE) in selitems:
                print(f"Table selecting row {i}")
                self.table.selectRow(i)
        self.selectingItems = False

    def tableSelectionChanged(self):
        if not self.selectingItems:
            # this gets the data items - the actual PDS4 product objects - selected in the table
            items = [x.data(PRIVATEDATAROLE) for x in self.table.selectedItems()]
            sel = []
            for i, x in enumerate(self.method.products):
                if x in items:
                    sel.append(i)
            self.method.selected = sel
            self.showSelectedItems()

    def timelineSelectionChanged(self):
        """timeline selection changed, we need to make the table sync up"""
        if not self.selectingItems:
            items = [x.data for x in self.timeline.getSelection()]
            sel = []
            for i, x in enumerate(self.method.products):
                if x in items:
                    sel.append(i)
            self.method.selected = sel
            self.showSelectedItems()

    def cameraChanged(self, i):
        self.method.camera = "PANCAM" if i == 0 else "AUPE"
        # not really necessary here because it only affects what happens when we scan
        self.onInputChanged()

    def recurseChanged(self, v):
        """recursion checkbox toggled"""
        self.method.recurse = (v != 0)

    def scanDir(self):
        """Scan the selected directory for PDS4 products and populate the model, refreshing the timeline and table"""
        try:
            self.method.loadLabelsFromDirectory()
            self.populateTableAndTimeline()
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            ui.log(str(e))

    def scanDirClicked(self):
        """Does a scanDir() if we confirm it"""
        if QMessageBox.question(self.parent(), "Rescan directory",
                                "This will clear all loaded products. Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.scanDir()

    def readClicked(self):
        """Read selected data, checking for validity, and generate output"""
        try:
            self.method.readSelectedData()
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            ui.log(str(e))

    def browseClicked(self):
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for products',
                                                         os.path.expanduser(self.method.dir))
        if res != '':
            self.fileEdit.setText(res)
            self.method.dir = res

    def onInputChanged(self):
        # ensure image is also using my mapping.
        if self.method.img is not None:
            self.method.img.setMapping(self.method.mapping)
        self.camCombo.setCurrentIndex(1 if self.method.camera == 'AUPE' else 0)

        print("Displaying image {}, mapping {}".format(self.method.img, self.method.mapping))
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)
