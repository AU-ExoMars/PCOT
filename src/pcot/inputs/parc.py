"""
The input method for PCOT Datum archives (items saved using the DatumStore/FileArchive
mechanism). These should have a MANIFEST file.
"""
import logging
import os
from typing import Optional, Dict, List

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QTableView, QPlainTextEdit, QLabel

import pcot
from pcot.dataformats import load
from pcot.imagecube import ChannelMapping
from pcot.inputs.inputmethod import InputMethod
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui import uiloader
from pcot.ui.canvas import Canvas
from pcot.ui.datawidget import DataWidget
from pcot.ui.inputs import MethodWidget
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore, Metadata

logger = logging.getLogger(__name__)


class PARCInputMethod(InputMethod):
    fname: Optional[str]
    itemname: Optional[str]
    manifest: Dict[str, Metadata]       # the file's manifest - only loaded from the file, never saved
    itemmeta: Optional[Metadata]        # manifest entry for the current item - saved, so we can show it without the file
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.fname = None
        self.itemname = None
        self.manifest = {}
        self.itemmeta = None
        self.mapping = ChannelMapping()

    @property
    def itemdesc(self) -> str:
        return self.itemmeta.description if self.itemmeta is not None else ''

    def setFileAndItem(self, fname, itemname='main'):
        """Used from scripts/library code and tests. Doesn't touch the file - the manifest (and
        so the item's metadata) are loaded by readData()."""
        self.fname = fname
        self.itemname = itemname
        self.manifest = {}
        self.itemmeta = None
        self.mapping = ChannelMapping()
        return self

    def loadManifest(self):
        if self.fname is not None:
            a = DatumStore(FileArchive(self.fname))
            self.manifest = a.manifest
        else:
            self.manifest = {}

    def updateItemMeta(self):
        """Set the current item's metadata from the manifest, which must already be loaded"""
        self.itemmeta = self.manifest.get(self.itemname)

    def readData(self):
        # the manifest is only loaded by the widget, so it may not be here (e.g. in batch mode)
        if self.itemname not in self.manifest:
            self.loadManifest()
        self.updateItemMeta()
        return load.parc(self.fname, self.itemname, self.input.idx)

    def getName(self):
        return "PARC"

    def missingPathReason(self) -> Optional[str]:
        if self.fname is not None and not os.path.isfile(self.fname):
            return f"File not found: {self.fname}{self._cachedDataSuffix()}"
        return None

    def serialise(self, internal):
        # The data itself isn't stored here: it's cached in self.data, which survives undo/redo
        # because input methods are deserialised into the existing objects.
        x = {'fname': self.fname, 'itemname': self.itemname,
             'itemmeta': self.itemmeta.serialise() if self.itemmeta is not None else None}
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        if data is not None:
            self.fname = data['fname']
            self.itemname = data['itemname']
            if data.get('itemmeta') is not None:
                self.itemmeta = Metadata.deserialise(data['itemmeta'])
            elif data.get('itemdesc'):
                # older documents only saved the description
                self.itemmeta = Metadata('', data['itemdesc'], '', None)
            else:
                self.itemmeta = None
            Canvas.deserialise(self, data)
        else:
            self.fname = None
            self.itemname = None
            self.itemmeta = None

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        if d.parc.filename is not None:
            self.fname = d.parc.filename
            self.itemname = d.parc.itemname   # this will be defaulted to 'main' by the PARCDictType
            self.itemmeta = None    # set by readData() when the item is loaded
            return True
        return False

    def createWidget(self):
        return PARCMethodWidget(self)


class Row:
    """A row in the item table"""
    def __init__(self, key: str, label: str, meta: Optional[Metadata], enabled: bool):
        self.key = key              # item name in the archive
        self.label = label          # what we show for it
        self.meta = meta            # may be None if we don't know anything about the item
        self.enabled = enabled      # can it be double-clicked to load it?


class Model(QtCore.QAbstractTableModel):
    def __init__(self, parent, rows: List[Row]):
        super().__init__(parent)
        self.rows = rows

    def rowCount(self, parent):
        return len(self.rows)

    def columnCount(self, parent):
        return 4

    def flags(self, index):
        if index.isValid() and self.rows[index.row()].enabled:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.NoItemFlags      # shown greyed out, and can't be selected

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            row = self.rows[index.row()]
            if index.column() == 0:
                return row.label
            meta = row.meta
            if meta is None:
                return ''
            if index.column() == 1:
                return meta.description
            elif index.column() == 2:
                return meta.datumtype
            else:
                return meta.created.strftime('%Y-%m-%d %H:%M:%S') if meta.created is not None else ''
        return None


class PARCMethodWidget(MethodWidget):
    openButton: QPushButton
    status: QLabel
    tableView: QTableView
    data: DataWidget
    itemDescription: QPlainTextEdit

    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi("ui/inputs/inputparc.ui", self)
        self.manifestError = None   # error message if the manifest couldn't be read
        self.openButton.clicked.connect(self.openFile)
        self.tableView.doubleClicked.connect(self.itemSelected)
        self.showManifest()
        self.tableView.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)

        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the document, which is stored in the manager,
        # which we get from the input, which we get from the method. Ugh.
        # Indirection, eh?
        self.data.canvas.setGraph(m.input.mgr.doc.graph)
        self.data.canvas.setPersister(m)

        self.syncIfActive()

    def onClose(self):
        super().onClose()
        self.data.canvas.onClose()

    def onInputChanged(self):
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        # get() rather than .data, so the data is read even if nothing in the graph reads this
        # input (or autorun is off). It's done before showing the description, which readData() sets.
        datum = self.method.get()
        self.itemDescription.setPlainText(self.method.itemdesc)
        self.data.display(datum)
        # the file or item may have changed (e.g. by undo/redo), or the item may have turned out
        # not to be in the file, so redo the table and status
        self.showManifest()

    def _fileExists(self):
        return self.method.fname is not None and os.path.isfile(self.method.fname)

    def _hasData(self):
        d = self.method.data
        return d is not None and not d.isNone()

    def _rows(self) -> List[Row]:
        """If the file is there, all its items can be loaded. Otherwise we can only show the current
        item, using the metadata saved in the document, and it can't be changed."""
        m = self.method
        if self._fileExists():
            rows = [Row(k, k, m.manifest[k], True) for k in sorted(m.manifest)]
            if m.itemname is not None and m.itemname not in m.manifest and self._hasData():
                # the data we have is for an item which isn't in the file (any more)
                rows.append(Row(m.itemname, f"{m.itemname} (not in file)", m.itemmeta, False))
            return rows
        elif m.itemname is not None:
            return [Row(m.itemname, m.itemname, m.itemmeta, False)]
        return []

    def showManifest(self):
        """Show the item table and status. The manifest is reread from the file if it's there, in case
        the file has changed."""
        self.manifestError = None
        if self._fileExists():
            try:
                self.method.loadManifest()
            except Exception as e:
                logger.warning(f"Cannot read manifest of {self.method.fname}: {e}")
                self.manifestError = str(e)
                self.method.manifest = {}
        else:
            self.method.manifest = {}
        rows = self._rows()
        self.tableView.setModel(Model(self, rows))
        for i, r in enumerate(rows):
            if r.enabled and r.key == self.method.itemname:
                self.tableView.selectRow(i)
        self.status.setText(self.statusText())

    def statusText(self) -> str:
        m = self.method
        if m.fname is None:
            return "No file selected. Use Open File to choose a PARC file."
        name = os.path.basename(m.fname)
        item = f"'{m.itemname}'"
        if not self._fileExists():
            if self._hasData():
                return (f"{name} was not found. Showing item {item} from the previously loaded data; "
                        f"other items can't be loaded until the file is available again.")
            return f"{name} was not found, and there is no previously loaded data."
        if self.manifestError is not None:
            return f"Cannot read {name}: {self.manifestError}"
        if m.itemname is None:
            return f"Double-click an item in {name} to load it."
        if m.itemname not in m.manifest:
            if self._hasData():
                return (f"Item {item} is not in {name}. Showing the previously loaded data; "
                        f"double-click an item to load a different one.")
            return f"Item {item} is not in {name}. Double-click an item to load it."
        if self._hasData():
            return f"Showing item {item} from {name}."
        err = m.input.exception
        return f"Item {item} could not be loaded from {name}" + (f": {err}" if err else ".")

    def openFile(self):
        # use an file dialog to select a file
        res = QtWidgets.QFileDialog.getOpenFileName(self,
                                                    'Open file',
                                                    os.path.expanduser(pcot.config.getDefaultDir('images')),
                                                    "PCOT datum archive files (*.parc)",
                                                    options=pcot.config.getFileDialogOptions())
        if res[0] != '':
            self.method.mark()
            self.method.fname = res[0]
            self.showManifest()
            pcot.config.setDefaultDir('images', os.path.dirname(res[0]))
            self.refreshMissingIndicator()

    def itemSelected(self):
        rows = self.tableView.model().rows
        row = rows[self.tableView.currentIndex().row()]
        if not row.enabled:     # shouldn't happen, as disabled rows can't be selected
            return
        self.method.mark()
        self.method.itemname = row.key
        # set the metadata here rather than relying on readData(), which only runs if the graph
        # is performed (autorun on) and something reads this input.
        self.method.updateItemMeta()
        # _sync() invalidates the cached data and reruns the graph, which reads the new item
        pcot.config.setDefaultDir('images', os.path.dirname(self.method.fname))
        self._sync()
