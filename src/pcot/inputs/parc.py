"""
The input method for PCOT Datum archives (items saved using the DatumStore/FileArchive
mechanism). These should have a MANIFEST file.
"""
import logging
import os
from typing import Optional, Tuple, Dict

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Qt

import pcot
from pcot.dataformats import load
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping
from pcot.inputs.inputmethod import InputMethod
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui import uiloader
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore, Metadata

logger = logging.getLogger(__name__)


class PARCInputMethod(InputMethod):
    datum: Optional[Datum]
    fname: Optional[str]
    itemname: Optional[str]
    manifest: Dict[str, Tuple[str, str, str]]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.fname = None
        self.itemname = None
        self.datum = None
        self.manifest = {}
        self.mapping = ChannelMapping()

    def setFileAndItem(self, fname, itemname='main'):
        self.fname = fname
        self.itemname = itemname
        self.mapping = ChannelMapping()
        return self

    def loadManifest(self):
        if self.fname is not None:
            a = DatumStore(FileArchive(self.fname))
            self.manifest = a.manifest
        else:
            self.manifest = {}

    def readData(self):
        self.datum = load.parc(self.fname, self.itemname, self.input.idx)
        return self.datum

    def getName(self):
        return "PARC"

    def serialise(self, internal):
        x = {'fname': self.fname, 'itemname': self.itemname}
        if internal:
            x['datum'] = self.datum.serialise() if self.datum is not None else None
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        if data is not None:
            self.fname = data['fname']
            self.itemname = data['itemname']
            if internal and data['datum'] is not None:
                self.datum = Datum.deserialise(data['datum'], self._document())
            else:
                self.datum = None
            Canvas.deserialise(self, data)
        else:
            self.fname = None
            self.itemname = None
            self.datum = None

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        if d.parc.filename is not None:
            self.fname = d.parc.filename
            self.itemname = d.parc.itemname   # this will be defaulted to 'main' by the PARCDictType
            return True
        return False

    def createWidget(self):
        return PARCMethodWidget(self)


class Model(QtCore.QAbstractTableModel):
    def __init__(self, parent, manifest):
        super().__init__(parent)
        self.manifest = manifest

    def rowCount(self, parent):
        return len(self.manifest)

    def columnCount(self, parent):
        return 4

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            # get a sorted list of the manifest keys
            keys = sorted(list(self.manifest.keys()))
            # and return the appropriate item
            item: Metadata = self.manifest[keys[index.row()]]
            print(item)
            if index.column() == 0:
                return keys[index.row()]            # column zero is the key
            else:
                tmp = [item.description, item.datumtype, item.created.strftime('%Y-%m-%d %H:%M:%S')]
                return tmp[index.column()-1]         # columns 1, 2, 3 are the size, type, date


class PARCMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi("inputparc.ui", self)
        self.openButton.clicked.connect(self.openFile)
        self.tableView.doubleClicked.connect(self.itemSelected)
        self.tableView.setModel(Model(self, m.manifest))
        self.tableView.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the document, which is stored in the manager,
        # which we get from the input, which we get from the method. Ugh.
        # Indirection, eh?
        self.data.canvas.setGraph(m.input.mgr.doc.graph)
        self.data.canvas.setPersister(m)

        self.onInputChanged()

    def onInputChanged(self):
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.data.display(self.method.datum)

    def openFile(self):
        # use an file dialog to select a file
        res = QtWidgets.QFileDialog.getOpenFileName(self,
                                                    'Open file',
                                                    os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                    "PCOT datum archive files (*.parc)",
                                                    options=pcot.config.getFileDialogOptions())
        if res[0] != '':
            self.method.fname = res[0]
            self.method.loadManifest()
            self.tableView.setModel(Model(self, self.method.manifest))
            pcot.config.setDefaultDir('pcotfiles', os.path.dirname(res[0]))

    def itemSelected(self):
        self.method.mark()
        self.method.datum = None
        model = self.tableView.model()
        keys = sorted(list(model.manifest.keys()))
        self.method.itemname = keys[self.tableView.currentIndex().row()]
        self.method.get()
        pcot.config.setDefaultDir('images', os.path.dirname(self.method.fname))
        self.onInputChanged()
