import os
from pathlib import Path
from typing import Optional, List

from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QValidator
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem

from proctools.products.loader import ProductLoader

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.ui.linear import LinearSetEntity, entityMarkerInitSetup, entityMarkerPaintSetup, TickRenderer
from pcot.dataformats.pds4 import PDS4Product


class PDS4ImageInputMethod(InputMethod):
    """PDS4 inputs are unusual in that they can come from several PDS4 products, not a single file."""

    # Here is the data model. This all gets persisted.

    img: Optional[ImageCube]        # the output - just image supported for now.

    products: List[PDS4Product]     # list of PDS4 products found under the directory "dir". Not all will be selected.
    selected: List[int]             # indices of selected items in the above list

    dir: Optional[str]              # the directory we have got the data from; just used to set up the widget
    mapping: ChannelMapping         # the mapping for the canvas
    recurse: bool   # when scanning directories, should we do it recursively?

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.products = []
        self.selected = []
        self.dir = None
        self.mapping = ChannelMapping()
        self.recurse = False

    def loadLabelsFromDirectory(self):
        """This will actually load data from the directory into the linear widget. """
        if self.dir is not None:
            try:
                loader = ProductLoader()
                loader.load_products(Path(self.dir), recursive=self.recurse)
                # Retrieve all loaded PAN-PP-220/spec-rad products as instances of
                # proctools.products.pancam:SpecRad; sub in the mnemonic of the product you're after
                for dat in loader.all("spec-rad"):
                    m = dat.meta

                    prod = PDS4Product(m.sol_id, m.seq_num, m.filter_cwl, m.filter_id,
                                       m.camera, m.rmc_ptu)
            except Exception as e:
                ui.log(str(e))
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
        raise NotImplementedError   #TODO
        self.mapping = ChannelMapping()

    def createWidget(self):
        return PDS4ImageMethodWidget(self)

    def serialise(self, internal):
        x = {'recurse': self.recurse,
             'selected': self.selected,
             'products': [x.serialise() for x in self.products],
             'dir': self.dir,
             'mapping': self.mapping.serialise()}
        if internal:
            x['image'] = self.img
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.recurse = data['recurse']
        self.selected = data['selected']
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

        # prescan the directory?? Not now; any data will
        # be serialised in the method object - we only do
        # this when we want to get new data.

        # self.method.loadLabelsFromDirectory()

        # connect signals

        self.recurseBox.stateChanged.connect(self.recurseChanged)
        self.browse.clicked.connect(self.browseClicked)
        self.scanDirButton.clicked.connect(self.scanDirClicked)
        self.readButton.clicked.connect(self.readClicked)

        # set up the timeline and table

        self.initTimeline()
        self.initTable()

        # add some test data to the linear widget
        items = []
        for day in range(10):
            xx = [LinearSetEntity(day, i, f"filt{i}", None) for i in range(10)]
            items += xx
            items.append(ExampleLinearSetEntityA(day + 0.5, 12, "foon", None))
        self.timeline.setItems(items)
        self.timeline.rescale()
        self.timeline.rebuild()

    def initTable(self):
        """initialise the table of PDS4 products"""
        cols = ["foo", "bar", "baz"]
        t = self.table
        t.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        t.verticalHeader().setVisible(False)
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)

    def addTableRow(self, strs):
        self.table.insertRow(self.table.rowCount())
        n = self.table.rowCount()-1
        for i, x in enumerate(strs):
            self.table.setItem(n, i, QTableWidgetItem(x))

    def initTimeline(self):
        """initialise the PDS4 product timeline"""
        # create some tick renderers for the widget
        # this is for big text when the ticks are far apart
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=20, textcol=(0, 0, 255), minxdist=50,
                                                   textgenfunc=lambda x: f"sol {int(x)}"))
        # this is the same, but the text is smaller and renders when the ticks are close together
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=10, textcol=(0, 0, 255), maxxdist=50,
                                                   textgenfunc=lambda x: f"{int(x)}"))

        # and these are intermediate values
        self.timeline.addTickRenderer(
            TickRenderer(spacing=0.1, fontsize=8, textoffset=30, linecol=(230, 230, 230), linelen=0.5, minxdist=10,
                         textgenfunc=lambda x: f"{int(x*10+0.3)%10}", textalways=True))
        self.timeline.setYOffset(100)   # make room for axis text

    def populateTableAndTimeline(self):
        """Refresh the table and timeline to reflect what's stored in the method."""
        # first the table.
        self.table.clearContents()

    def recurseChanged(self, v):
        """recursion checkbox toggled"""
        self.method.recurse = (v != 0)

    def scanDirClicked(self):
        """Scan the selected directory for PDS4 products and populate the model, refreshing the timeline and table"""
        if QMessageBox.question(self.parent(), "Rescan directory",
                                "This will clear all loaded products. Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.method.loadLabelsFromDirectory()
        pass

    def readClicked(self):
        """Read selected data, checking for validity, and generate output"""
        pass

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
        print("Displaying image {}, mapping {}".format(self.method.img, self.method.mapping))
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)
