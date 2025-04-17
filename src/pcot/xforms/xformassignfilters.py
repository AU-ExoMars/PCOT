import logging
from typing import List, Any

from PySide2 import QtCore
from PySide2.QtCore import QAbstractTableModel, QModelIndex, Signal, QItemSelectionModel, QItemSelection

from pcot import ui
from pcot.cameras import getCamera, getCameraNames
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType
from pcot.sources import Source
from pcot.ui.tablemodel import TableModel
from pcot.ui.tabs import Tab
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype

logger = logging.getLogger(__name__)


@xformtype
class XFormAssignFilters(XFormType):
    """
    This node can be used to manually assign a camera and filter data to bands
    in an image if this could not be done automatically. For example, the data
    could have been loaded from an RGB image in PNG format, or the regular
    expression tools in the multifile input may not have been sufficient. It
    can also be useful in testing.

    Be careful when using this - it can mess up correct information quite easily.
    """

    def __init__(self):
        super().__init__("assignfilters", "utility", "0.0.0")
        self.addInputConnector("", Datum.IMG, desc="input image")
        self.addOutputConnector("", Datum.IMG, desc="output image")

        self.params = TaggedDictType(
            filters=("Names of filters", TaggedListType(str, [], '')),
            camera=("Name of camera", str, 'PANCAM'),
        )

    def init(self, node):
        node.channels = 0   # number of channels to be mapped

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            node.channels = 0
            node.setOutput(0, Datum.null)
            return

        node.channels = img.channels

        # get the camera by name
        camera = getCamera(node.params.camera)
        if camera is None:
            ui.log(f"Camera {node.params.camera} not found")
            node.setOutput(0, Datum.null)
            return

        # make a shallow copy
        img = img.shallowCopy()

        cam_filters = sorted(list(camera.params.filters.keys()))

        # if any filters are not in the camera, remove them
        node.params.filters._values = [f for f in node.params.filters if f in cam_filters]

        # if any filters are not in the image, add them
        for f in cam_filters:
            if f not in node.params.filters:
                node.params.filters.append(f)

        # get the filters by name and build a multiband source
        for i, f in enumerate(node.params.filters):
            # is there an input index and external in any of the existing sources? Record if so.
            # Note that we are working on the MultibandSource in place.
            if i < len(img.sources.sourceSets):
                existing_sources = img.sources.sourceSets[i]
                existing_inps = set([s for s in existing_sources if s.inputIdx is not None and s.external is not None])
                if len(existing_inps) > 1:
                    ui.log(f"Multiple input indices found for filter {f} in band {i} - cannot assign")
                    node.setOutput(0, Datum.null)
                    return
                existing = next(iter(existing_inps), None)

                f = camera.getFilter(f)
                if f is None:
                    ui.log(f"Filter {f} not found in camera {node.params.camera}")
                    node.setOutput(0, Datum.null)
                    return
                s = Source().setBand(f)
                # replace the existing source if there is one, otherwise just add the new one
                if existing is not None:
                    s.setInputIdx(existing.inputIdx).setExternal(existing.external)
                    existing_sources.sourceSet.remove(existing)
                existing_sources.sourceSet.add(s)

        node.setOutput(0, Datum(Datum.IMG, img))

    def createTab(self, xform, window):
        return TabAssignFilters(xform, window)


class TableModelStringList(QAbstractTableModel):
    """Table model for a list of strings with indices. We rely on the calling tab to handle
    changing the object ordering (all this model is used for)"""

    changed = Signal()

    def __init__(self, tab: Tab, data: List[str], indexname: str, colname: str):
        QAbstractTableModel.__init__(self)
        self.tab = tab
        self.indexname = indexname
        self.colname = colname
        self.d = data
        # items greater than or equal to this are shown with a blank index; they aren't relevant
        # because they aren't going to be mapped to actual bands in the image.
        self.maxitems = 100000

    def rowCount(self, parent=...):
        return len(self.d)

    def columnCount(self, parent=...):
        return 2

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                if index.row() >= self.maxitems:
                    return "-"
                return str(index.row())
            else:
                return self.d[index.row()]
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return self.indexname
            else:
                return self.colname

    def selectRow(self, r):
        sel = QItemSelection(self.model.index(r, 0), self.model.index(r, 2))
        self.w.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)

    def _item_swap(self, a, b):
        self.d[a], self.d[b] = self.d[b], self.d[a]


class TabAssignFilters(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, "tabassignfilters.ui")
        self.model = TableModelStringList(self, node.params.filters, "Band", "Filter")
        self.w.table.setModel(self.model)
        self.model.maxitems = node.channels
        self.w.table.setColumnWidth(0, 50)
        self.w.cameraCombo.clear()
        self.w.cameraCombo.addItems(getCameraNames())
        self.w.cameraCombo.currentIndexChanged.connect(self.cameraChanged)
        self.w.up.pressed.connect(self.upPressed)
        self.w.down.pressed.connect(self.downPressed)
        self.nodeChanged()

    def cameraChanged(self, i):
        self.node.params.camera = self.w.cameraCombo.itemText(i)
        self.changed()

    def getSelected(self):
        return [mi.row() for mi in self.w.table.selectionModel().selectedRows()]

    def upPressed(self):
        self.mark()
        f = self.node.params.filters
        for r in self.getSelected():
            if r > 0:
                f[r-1], f[r] = f[r], f[r-1]
            self.w.table.selectRow(r-1)
        self.changed()

    def downPressed(self):
        self.mark()
        f = self.node.params.filters
        for r in self.getSelected():
            if r < len(f) - 1:
                f[r], f[r+1] = f[r+1], f[r]
            self.w.table.selectRow(r+1)
        self.changed()

    def onNodeChanged(self):
        self.model.maxitems = self.node.channels
        self.w.cameraCombo.setCurrentText(self.node.params.camera)
        self.w.table.viewport().update()
