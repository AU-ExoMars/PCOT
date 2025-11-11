import logging
from typing import List, Any, Tuple, Dict

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
from pcot.xform import XFormType, xformtype, XFormException

logger = logging.getLogger(__name__)


def getFiltersFromCamera(node):
    """
    Make sure the filter list is correct - will override any existing mapping
    """
    camera = getCamera(node.params.camera)
    if camera is None:
        ui.log(f"Camera {node.params.camera} not found")
        node.setOutput(0, Datum.null)
        return

    cam_filters = sorted(list(camera.params.filters.keys()))

    # if any filters are not in the camera, remove them
    node.params.filters._values = [f for f in node.params.filters if f in cam_filters]

    # if any filters are not in the image, add them
    for f in cam_filters:
        if f not in node.params.filters:
            node.params.filters.append(f)


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
        node.wavelengths_in_image = []  # wavelengths in the image

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            node.channels = 0
            node.setOutput(0, Datum.null)
            return

        node.channels = img.channels

        # make a shallow copy
        img = img.shallowCopy()

        getFiltersFromCamera(node)

        # iterate over the image bands and store the wavelengths
        node.wavelengths_in_image = [img.wavelength(i) for i in range(0,img.channels)]

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

                camera = getCamera(node.params.camera)
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


class TableModelAssignFilters(QAbstractTableModel):
    """Table model for a list of string pairs with indices. We rely on the calling tab to handle
    changing the object ordering (all this model is used for)"""

    changed = Signal()

    def __init__(self, tab: Tab, filternames: List[str], filterwavelengthdict: Dict[str, str],
                 indexname: str, colnames: List[str]):
        QAbstractTableModel.__init__(self)
        self.tab = tab
        self.indexname = indexname
        self.colnames = colnames
        self.nstrcols = len(colnames)
        self.filternames = filternames
        self.filterwavelengthdict = filterwavelengthdict
        # items greater than or equal to this are shown with a blank index; they aren't relevant
        # because they aren't going to be mapped to actual bands in the image.
        self.maxitems = 100000

    def rowCount(self, parent=...):
        return len(self.filternames)

    def columnCount(self, parent=...):
        return self.nstrcols+1   # number of string cols plus the index col

    def data(self, index, role):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()

        if role == QtCore.Qt.DisplayRole:
            if c == 0:
                # displaying the index column
                if r >= self.maxitems:
                    return "-"
                return str(r)
            elif c == 1:
                # displaying the actual data
                return self.filternames[r]
            else:
                # displaying the filter wavelength which we look up from the filter name
                return self.filterwavelengthdict[self.filternames[r]]
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                if section == 0:
                    return self.indexname
                else:
                    return self.colnames[section-1]
            else:
                # no headers in the vertical orientation
                return None

    def selectRow(self, r):
        # nstrcols+2 because there's an index row, and some string rows, and +1 because the end of the interval
        # is exclusive.
        sel = QItemSelection(self.model.index(r, 0), self.model.index(r, self.nstrcols+2))
        self.w.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)

    def _item_swap(self, a, b):
        self.filternames[a], self.filternames[b] = self.filternames[b], self.filternames[a]


class TabAssignFilters(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, "tabassignfilters.ui")

        self.w.table.setColumnWidth(0, 50)
        self.w.cameraCombo.clear()
        self.w.cameraCombo.addItems(getCameraNames())
        self.w.cameraCombo.currentIndexChanged.connect(self.cameraChanged)
        self.w.up.pressed.connect(self.upPressed)
        self.w.down.pressed.connect(self.downPressed)
        self.w.guessButton.pressed.connect(self.guessPressed)
        self.setFilters()
        self.nodeChanged()

    def setFilters(self):
        node = self.node
        camera = getCamera(node.params.camera)
        filterwavelengthdict = {f: camera.getFilter(f).cwl for f in node.params.filters}
        self.model = TableModelAssignFilters(self,
                                             node.params.filters, filterwavelengthdict,
                                             "Band", ["Filter", "Wavelength"])
        self.w.table.setModel(self.model)
        self.model.maxitems = node.channels

    def cameraChanged(self, i):
        self.node.params.camera = self.w.cameraCombo.itemText(i)
        getFiltersFromCamera(self.node)
        self.setFilters()
        self.changed()

    def getSelected(self):
        return [mi.row() for mi in self.w.table.selectionModel().selectedRows()]

    def guessPressed(self):
        self.mark()
        out = []
        # get the camera by name
        camera = getCamera(self.node.params.camera)
        if camera is None:
            ui.log(f"Camera {self.node.params.camera} not found")
            return
        # for each band in the image, get its wavelength and try to find a matching filter
        for i in self.node.wavelengths_in_image:
            # find the filter with the closest wavelength
            f = camera.getFilter(i, search='cwl')
            if f is not None:
                out.append(f.name)
            else:
                raise XFormException("DATA", "No filter found for wavelength {}".format(i))
        self.node.params.filters._values = out
        self.changed()

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
