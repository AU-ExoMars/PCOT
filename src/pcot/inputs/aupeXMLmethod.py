import os
from pathlib import Path
from typing import Optional, List
import logging

import numpy as np
from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt

import pcot
from pcot import ui, dq
from pcot.datum import Datum
from pcot.inputs.inputmethod import InputMethod
from pcot.sources import Source, StringExternal, SourceSet
from pcot.ui import uiloader
from pcot.ui.inputs import MethodWidget
from pcot.value import Value

logger = logging.getLogger(__name__)


def _load(fname) -> float:
    """Read the exposure time from an AUPE XML metadata file. Raises if it can't be found."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(fname)
    root = tree.getroot()
    cont = root.find("context")

    attribs = cont.findall("attribute")
    for x in attribs:
        if x.get("name") == "metadata":
            mds = x.get("value").split(";")
            mds = list(filter(lambda x: len(x) > 1, map(lambda x: x.split("="), mds)))
            mds = {x[0]: x[1] for x in mds}
            if "ImageMetadata" in mds:
                md = mds["ImageMetadata"].split("|")
                md = dict(zip(md[::2], md[1::2]))
                return float(md["exposure_time"])
    raise ValueError("no exposure_time in ImageMetadata")


def _listXMLFiles(dr) -> List[str]:
    """List XML files in a directory; propagates any exception (e.g. dir doesn't exist)."""
    return sorted([f for f in os.listdir(dr) if os.path.isfile(os.path.join(dr, f))
                   and f.lower().endswith(".xml")])


class AUPEXMLMethod(InputMethod):
    """Reads exposure times from a set of AUPE XML metadata files in a single directory,
    producing a vector (Datum.NUMBER) with one element per file, in the order of the
    file list. Files which can't be read give NODATA elements."""
    dir: Optional[Path]
    files: List[str]

    def __init__(self, inp):
        super().__init__(inp)
        # directory we're looking at
        tmp = pcot.config.getDefaultDir('images')
        self.dir = Path(tmp) if tmp is not None else None
        if not self.dir or not self.dir.is_dir():
            self.dir = Path.home()
        # files we have checked in the file list
        self.files = []

    def missingPathReason(self) -> Optional[str]:
        return self._missingDirFilesReason(self.dir, self.files)

    def setFileNames(self, directory, fnames: List[str]) -> InputMethod:
        """Used from external code to set the directory and the (ordered) list of files in it"""
        self.dir = Path(directory)
        self.files = list(fnames)
        return self

    def readData(self) -> Datum:
        if self.dir is None or len(self.files) == 0:
            return Datum.null

        ns = np.zeros(len(self.files), dtype=np.float32)
        dqs = np.full(len(self.files), dq.NOUNCERTAINTY, dtype=np.uint16)
        sources = []
        failed = []
        for i, f in enumerate(self.files):
            path = os.path.abspath(os.path.join(str(self.dir), f))
            logger.debug(f"Reading AUPE XML data from {path}")
            try:
                ns[i] = _load(path)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {path}: {e}")
                failed.append(f)
                dqs[i] |= dq.NODATA
            extern = StringExternal("AUPEXML", path)
            sources.append(Source().setInputIdx(self.input.idx).setExternal(extern))

        if failed:
            ui.warn(f"Could not read exposure time from {len(failed)} file(s), "
                    f"marked as NODATA: {', '.join(failed)}")

        return Datum(Datum.NUMBER, Value(ns, np.zeros_like(ns), dqs), SourceSet(sources))

    def serialise(self, internal):
        # the data itself isn't stored here - Input.serialise() saves the active method's
        # datum into the document, and undo/redo leaves it in place in this object.
        # The file list is copied (here and in deserialise) because the undo stack stores
        # these dicts as-is, and the widget reorders the list in place.
        return {
            "dir": str(self.dir) if self.dir is not None else None,
            "files": list(self.files),
        }

    def deserialise(self, data, internal):
        self.dir = Path(data["dir"]) if data.get("dir") is not None else None
        self.files = list(data.get("files", []))

    def getName(self):
        return "AUPE XML"

    def createWidget(self):
        return AUPEXMLWidget(self)


class AUPEXMLWidget(MethodWidget):
    dir: QtWidgets.QLineEdit

    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi('ui/inputs/inputaupexml.ui', self)
        self.model = None
        # all the XML files in the current directory
        self.allFiles = []

        self.getinitial.clicked.connect(self.getInitial)
        self.dir.editingFinished.connect(self.dirChanged)
        self.upButton.clicked.connect(lambda: self.moveSelected(-1))
        self.downButton.clicked.connect(lambda: self.moveSelected(1))

        # not used for vector data, but DataWidget has one and it needs setting up
        self.data.canvas.setGraph(m.input.mgr.doc.graph)
        self.data.canvas.setPersister(m)

        self.filelist.setMinimumWidth(300)
        pcot.ui.decorateSplitter(self.splitter, 1)

        self.syncIfActive()

    def onClose(self):
        super().onClose()
        self.data.canvas.onClose()

    def onInputChanged(self):
        self.refreshFileList()
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.data.display(self.method.get())

    def getInitial(self):
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for AUPE XML files',
                                                         os.path.expanduser(str(self.method.dir)),
                                                         options=pcot.config.getFileDialogOptions())
        if res != '':
            self.selectDir(res, True)

    def dirChanged(self):
        # directory text changed manually - if the dir exists, go there,
        # otherwise reset this text to what it was before (the method's dir)
        newdir = Path(self.dir.text())
        if newdir.is_dir():
            self.selectDir(newdir)
        else:
            self.dir.setText(str(self.method.dir))

    def refreshFileList(self):
        """Populate the file list from self.method.dir, without ever mutating that directory.
        If it can't be read (typically a document from another machine), just show an empty
        list plus any selected-but-missing files - the banner and tab button explain why."""
        dr = self.method.dir
        self.dir.setText(str(dr) if dr is not None else "")
        try:
            self.allFiles = _listXMLFiles(dr) if dr is not None else []
        except Exception as e:
            logger.info(f"AUPE XML: configured directory not available ({dr}): {e}")
            self.allFiles = []
        self.buildModel()
        self.refreshMissingIndicator()

    def selectDir(self, dr, setDefaultDir=False):
        """Called when the user explicitly picks a new directory - dr becomes the new,
        real value of self.method.dir."""
        try:
            _listXMLFiles(dr)
        except Exception as e:
            ui.error(str(e))
            return
        dr = Path(os.path.realpath(dr))
        if self.method.dir != dr:
            # changing directory resets the selection, which is an undoable change
            self.method.mark()
            self.method.files = []
            self.method.dir = dr
        if setDefaultDir:
            pcot.config.setDefaultDir('images', self.method.dir)
        self.onInputChanged()

    def buildModel(self):
        """Build the file list. Checked files come first, in the order of the output vector
        (self.method.files) and labelled with their element index; then the remaining files
        in the directory, unchecked. The filename itself is stored in UserRole, because the
        displayed text includes the index."""
        self.model = QtGui.QStandardItemModel(self.filelist)

        # selected files that aren't in the current listing are shown in red (in their
        # proper position), so the user can see exactly what's missing rather than the
        # selection silently vanishing.
        redBrush = QtGui.QBrush(QtGui.QColor(200, 0, 0))
        for i, x in enumerate(self.method.files):
            item = QtGui.QStandardItem(f"[{i}] {x}")
            item.setData(x, Qt.ItemDataRole.UserRole)
            item.setCheckable(True)
            item.setCheckState(Qt.CheckState.Checked)
            if x not in self.allFiles:
                item.setForeground(redBrush)
                item.setToolTip("This file could not be found")
            self.model.appendRow(item)

        for x in self.allFiles:
            if x not in self.method.files:
                item = QtGui.QStandardItem(x)
                item.setData(x, Qt.ItemDataRole.UserRole)
                item.setCheckable(True)
                self.model.appendRow(item)

        self.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)

    def checkedChanged(self):
        # the checked items have changed. Because the checked files are always at the top
        # of the list in vector order, reading them off in list order keeps the existing
        # order, removes any unchecked file and appends any newly checked one to the end.
        self.method.mark()
        self.method.files = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                self.method.files.append(item.data(Qt.ItemDataRole.UserRole))
        self.onInputChanged()

    def moveSelected(self, delta):
        """Move the selected file up (delta=-1) or down (delta=1) in the output vector"""
        idx = self.filelist.currentIndex()
        if not idx.isValid():
            return
        i = idx.row()
        j = i + delta
        files = self.method.files
        # only checked files (the first len(files) rows) can be moved, and only within that block
        if i >= len(files) or j < 0 or j >= len(files):
            return
        self.method.mark()
        files[i], files[j] = files[j], files[i]
        self.onInputChanged()
        # keep the moved file selected so it can be moved repeatedly
        self.filelist.setCurrentIndex(self.model.index(j, 0))
