import logging
from dataclasses import dataclass
from typing import Any, List

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, Signal, Qt
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import QSpinBox, QStyledItemDelegate, QComboBox, QTableView

from pcot import ui
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource, nullSource, InputSource, NullSource, FilterOnlySource
from pcot.xform import xformtype, XFormType

DEFAULTSIZE = 256
MODES = ['flat', 'ripple-n', 'ripple-u', 'ripple-un']
DEFAULTMODE = 'flat'

logger = logging.getLogger(__name__)


@dataclass
class ChannelData:
    """These are the items stored in the array we generate the image from: one for each band"""
    n: float = 0.0  # nominal value, used as multiplier for sine wave in ripple-n and ripple-un
    u: float = 0.0  # uncertainty of value, used as multiplier for sine wave in ripple-n and ripple-un
    cwl: int = 100  # centre wavelength
    mode: str = 'flat'  # mode - see node description

    def serialise(self):
        return self.n, self.u, self.cwl, self.mode

    @staticmethod
    def deserialise(t):
        return ChannelData(*t)


@xformtype
class XFormGen(XFormType):
    """Generate an image with given channel values. Can also generate patterns. Each band is given a nominal value
    and uncertainty, along with a centre frequency and a mode (for patterns).

    Modes are:

    * flat : N and U are used to fill the entire band
    * ripple-n: the N value is not a value, but a multiplier applied to distance from centre - the sine of this
    gives the value. The U value is generated as in 'flat'
    * ripple-u: as ripple-n, but this time U is used as a multiplier to generate the ripple pattern in uncertainty,
    while N is generated as in 'flat'
    * ripple-un: both values are ripple multipliers.

    """

    def __init__(self):
        super().__init__("gen", "source", "0.0.0")
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('imgwidth', 'imgheight')

    def createTab(self, n, w):
        return TabGen(n, w)

    def init(self, node):
        node.imgwidth = DEFAULTSIZE
        node.imgheight = DEFAULTSIZE
        # set the default data.
        node.imgchannels = [ChannelData()]

    def perform(self, node):
        # we'll fill these lists with data for the image bands nominal and uncertainty values
        ns = []
        us = []

        # build a meshgrid so we can make calculations based on position
        x, y = np.meshgrid(np.arange(node.imgwidth), np.arange(node.imgheight))
        cx = node.imgwidth / 2.0
        cy = node.imgheight / 2.0

        for chan in node.imgchannels:
            if chan.mode == 'flat':
                # flat mode is easy
                ns.append(np.full((node.imgheight, node.imgwidth), chan.n))
                us.append(np.full((node.imgheight, node.imgwidth), chan.u))
            elif chan.mode == 'ripple-n':
                # we build an expression based on position to get a ripple pattern in n
                d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                ns.append(np.sin(d) * 0.5 + 0.5)
                # but u remains flat
                us.append(np.full((node.imgheight, node.imgwidth), chan.u))
            elif chan.mode == 'ripple-u':
                # as above, but the other way around
                ns.append(np.full((node.imgheight, node.imgwidth), chan.n))
                d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                us.append(np.sin(d) * 0.5 + 0.5)
            elif chan.mode == 'ripple-un':
                # two ripples
                d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                ns.append(np.sin(d) * 0.5 + 0.5)
                d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                us.append(np.sin(d) * 0.5 + 0.5)

        # build the image arrays
        if len(ns) > 0:
            ns = np.dstack(ns).astype(np.float32)
            us = np.dstack(us).astype(np.float32)

            # construct Filter only sources - these don't have input data but do have a filter.
            sources = [FilterOnlySource(Filter(chan.cwl, 30, 1.0, idx=i)) for i, chan in enumerate(node.imgchannels)]
            # make and output the image
            node.img = ImageCube(ns, node.mapping, uncertainty=us, sources=MultiBandSource(sources))
            node.setOutput(0, Datum(Datum.IMG, node.img))
        else:
            node.img = None
            node.setOutput(0, Datum.null)

    def serialise(self, node):
        return {'chans': [x.serialise() for x in node.imgchannels]}

    def deserialise(self, node, d):
        node.imgchannels = [ChannelData.deserialise(x) for x in d['chans']]


class ComboBoxDelegate(QStyledItemDelegate):
    """ComboBox view inside of a Table. It only shows the ComboBox when it is
       being edited. Could be used for anything, actually.
    """

    def __init__(self, model, itemlist=None):
        super().__init__(model)
        self.model = model
        self.itemlist = itemlist

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.itemlist)
        editor.setCurrentIndex(0)
        editor.installEventFilter(self)
        # normally, the editor (the temporary combobox created when we double click) only closes when we
        # hit enter or click away. This makes sure it closes when an item is modified, so the change gets
        # sent to the model.
        editor.currentIndexChanged.connect(lambda: editor.close())
        return editor

    def setEditorData(self, editor, index):
        """Set the ComboBox's current index."""
        value = index.data(QtCore.Qt.DisplayRole)
        i = editor.findText(value)
        if i == -1:
            i = 0
        editor.setCurrentIndex(i)

    def setModelData(self, editor, model, index):
        """Set the table's model's data when finished editing."""
        value = editor.currentText()
        model.setData(index, value, QtCore.Qt.EditRole)


class Model(QAbstractTableModel):
    """This is the model which acts between the list of ChannelData items and the table view."""

    # custom signal used when we change data
    changed = Signal()

    def __init__(self, tab, _data: List[ChannelData]):
        QAbstractTableModel.__init__(self)
        self.header = ['N', 'U', 'CWL', 'mode']  # headers
        self.tab = tab  # the tab we're part of
        self.d = _data  # the list of data which is our model

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            # data labels down the side
            if orientation == QtCore.Qt.Vertical:
                return self.header[section]
            # channel indices along the top
            elif orientation == QtCore.Qt.Horizontal:
                return str(section)
        return None

    def rowCount(self, parent: QModelIndex) -> int:
        return len(self.header)

    def columnCount(self, parent: QModelIndex) -> int:
        return len(self.d)

    def data(self, index: QModelIndex, role: int) -> Any:
        """Called by the table view to get data to show"""
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None

        row = index.row()
        col = index.column()

        if row == 0:
            return self.d[col].n
        elif row == 1:
            return self.d[col].u
        elif row == 2:
            return self.d[col].cwl
        elif row == 3:
            return self.d[col].mode

        return None

    def move_left(self, n):
        """Move a row to the left. This stuff is messy."""
        if 0 < n < len(self.d):
            # I'm still not entirely sure what's going on in this line
            self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n - 1)
            self.d[n], self.d[n - 1] = self.d[n - 1], self.d[n]
            self.endMoveColumns()
            self.changed.emit()

    def move_right(self, n):
        """Move a row to the right. This stuff is messy."""
        if n < len(self.d) - 1:
            # I'm still not entirely sure what's going on in this line
            self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n + 2)
            self.d[n], self.d[n + 1] = self.d[n + 1], self.d[n]
            self.endMoveColumns()
            self.changed.emit()

    def add_item(self):
        """Add a new channeldata to the end of the list"""
        n = len(self.d)
        self.beginInsertColumns(QModelIndex(), n, n)
        self.d.append(ChannelData())
        self.endInsertColumns()
        self.changed.emit()
        return n

    def delete_item(self, n):
        """Remove a given channeldata"""
        if n < len(self.d):
            self.beginRemoveColumns(QModelIndex(), n, n)
            del self.d[n]
            self.endRemoveColumns()
            self.changed.emit()

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview or any item delegates"""
        if index.isValid():
            self.tab.mark()  # we do the undo mark here, before the data is changed
            row = index.row()
            col = index.column()
            d = self.d[col]
            # got a reference to the datum, now change it by looking at the row index to see which item.
            if row == 0:
                d.n = float(value)
            elif row == 1:
                d.u = float(value)
            elif row == 2:
                value = int(value)
                if value >= 0:
                    d.cwl = value
                else:
                    return False
            elif row == 3:
                d.mode = value

            # tell the view we changed
            self.dataChanged.emit(index, index, (QtCore.Qt.DisplayRole,))
            # and tell any other things too (such as the tab!)
            self.changed.emit()
            return True
        return False

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled


class SignalBlocker:
    """Handy class for blocking signals on several widgets at once"""

    def __init__(self, *args):
        self.objects = args

    def __enter__(self):
        for o in self.objects:
            o.blockSignals(True)

    def __exit__(self, exctype, excval, tb):
        for o in self.objects:
            o.blockSignals(False)


class GenTableView(QTableView):
    delete = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Delete:
            self.delete.emit()
        super().keyPressEvent(event)


class TabGen(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgen.ui')
        self.w.spinWidth.valueChanged.connect(self.sizeChanged)
        self.w.spinHeight.valueChanged.connect(self.sizeChanged)
        self.w.leftButton.clicked.connect(self.leftClicked)
        self.w.rightButton.clicked.connect(self.rightClicked)
        self.w.addButton.clicked.connect(self.addClicked)
        self.w.deleteButton.clicked.connect(self.deleteClicked)
        self.w.tableView.delete.connect(self.deleteClicked)

        self.model = Model(self, node.imgchannels)
        self.w.tableView.setModel(self.model)
        self.model.changed.connect(self.chansChanged)
        self.w.tableView.setItemDelegateForRow(3, ComboBoxDelegate(self.model, MODES))
        self.nodeChanged()

    def _getselcol(self):
        """Get the selected column, only if an entire column is selected - and if more than one is,
        only consider the first."""
        sel = self.w.tableView.selectionModel()
        if sel.hasSelection():
            if len(sel.selectedColumns()) > 0:
                col = sel.selectedColumns()[0].column()
                return col
        return None

    def leftClicked(self):
        """move left and then reselect the column we just moved"""
        if (col := self._getselcol()) is not None:
            self.model.move_left(col)
            self.w.tableView.selectColumn(col - 1)

    def rightClicked(self):
        """move right and then reselect the column we just moved"""
        if (col := self._getselcol()) is not None:
            self.model.move_right(col)
            self.w.tableView.selectColumn(col + 1)

    def addClicked(self):
        col = self.model.add_item()
        self.w.tableView.selectColumn(col)

    def deleteClicked(self):
        if (col := self._getselcol()) is not None:
            self.model.delete_item(col)

    def sizeChanged(self, _):
        self.mark()
        logger.info("Size Mark")
        self.node.imgwidth = self.w.spinWidth.value()
        self.node.imgheight = self.w.spinHeight.value()
        self.changed()

    def chansChanged(self):
        # we don't need to mark or set data here, it's already been done in the model!
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)

        with SignalBlocker(self.w.spinWidth, self.w.spinHeight):
            self.w.spinWidth.setValue(self.node.imgwidth)
            self.w.spinHeight.setValue(self.node.imgheight)

        self.w.canvas.display(self.node.img)
