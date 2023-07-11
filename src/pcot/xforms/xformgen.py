import logging
from dataclasses import dataclass
from typing import Any, List

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, Signal
from PySide2.QtWidgets import QSpinBox, QStyledItemDelegate, QComboBox

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
    n: float
    u: float
    cwl: int
    mode: str

    def serialise(self):
        return self.n, self.u, self.cwl, self.mode

    @staticmethod
    def deserialise(t):
        return ChannelData(*t)


@xformtype
class XFormGen(XFormType):
    """Generate an image with given channel values"""

    def __init__(self):
        super().__init__("gen", "source", "0.0.0")
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('imgwidth', 'imgheight')

    def createTab(self, n, w):
        return TabGen(n, w)

    def init(self, node):
        node.imgwidth = DEFAULTSIZE
        node.imgheight = DEFAULTSIZE
        node.imgchannels = [ChannelData(i * 0.1, 0, 0, DEFAULTMODE) for i in range(0, 4)]

    def perform(self, node):
        ns = []
        us = []

        x, y = np.meshgrid(np.arange(node.imgwidth), np.arange(node.imgheight))
        cx = node.imgwidth/2.0
        cy = node.imgheight/2.0

        for chan in node.imgchannels:
            if chan.mode == 'flat':
                ns.append(np.full((node.imgheight, node.imgwidth), chan.n))
                us.append(np.full((node.imgheight, node.imgwidth), chan.u))
            elif chan.mode == 'ripple-n':
                d = np.sqrt((x-cx)**2 + (y-cy)**2) * chan.n
                ns.append(np.sin(d)*0.5+0.5)
                us.append(np.full((node.imgheight, node.imgwidth), chan.u))
            else:
                d = np.sqrt((x-cx)**2 + (y-cy)**2) * chan.n
                ns.append(np.sin(d)*0.5+0.5)
                us.append(np.full((node.imgheight, node.imgwidth), chan.u))

        ns = np.dstack(ns).astype(np.float32)
        us = np.dstack(us).astype(np.float32)

        sources = [FilterOnlySource(Filter(chan.cwl, 30, 1.0, idx=i)) for i, chan in enumerate(node.imgchannels)]
        node.img = ImageCube(ns, node.mapping, uncertainty=us, sources=MultiBandSource(sources))
        node.setOutput(0, Datum(Datum.IMG, node.img))

    def serialise(self, node):
        return {'chans': [x.serialise() for x in node.imgchannels]}

    def deserialise(self, node, d):
        node.imgchannels = [ChannelData.deserialise(x) for x in d['chans']]


class ComboBoxDelegate(QStyledItemDelegate):
    """ComboBox view inside of a Table. It only shows the ComboBox when it is
       being edited.
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
    changed = Signal()

    def __init__(self, tab, _data: List[ChannelData]):
        QAbstractTableModel.__init__(self)
        self.header = ['Index', 'N', 'U', 'CWL', 'mode']
        self.tab = tab
        self.d = _data

    def headerData(self, col: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header[col]
        return None

    def rowCount(self, parent: QModelIndex) -> int:
        return len(self.d)

    def columnCount(self, parent: QModelIndex) -> int:
        return len(self.header)

    def data(self, index: QModelIndex, role: int) -> Any:
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None

        row = index.row()
        col = index.column()

        if col == 0:
            return row
        elif col == 1:
            return self.d[row].n
        elif col == 2:
            return self.d[row].u
        elif col == 3:
            return self.d[row].cwl
        elif col == 4:
            return self.d[row].mode

        return None

    def insertRows(self, row: int, count: int, parent: QModelIndex) -> bool:
        pass

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if index.isValid():
            self.tab.mark()    # we do the undo mark here, before the data is changed
            row = index.row()
            col = index.column()
            d = self.d[row]
            if col == 1:
                d.n = float(value)
            elif col == 2:
                d.u = float(value)
            elif col == 3:
                value = int(value)
                if value >= 0:
                    d.cwl = value
                else:
                    return False
            elif col == 4:
                d.mode = value

            self.dataChanged.emit(index, index, (QtCore.Qt.DisplayRole,))
            self.changed.emit()
            return True
        return False

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        if index.column() > 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.ItemIsSelectable


class SignalBlocker:
    def __init__(self, *args):
        self.objects = args

    def __enter__(self):
        for o in self.objects:
            o.blockSignals(True)

    def __exit__(self, exctype, excval, tb):
        for o in self.objects:
            o.blockSignals(False)


class TabGen(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabgen.ui')
        self.w.spinWidth.valueChanged.connect(self.sizeChanged)
        self.w.spinHeight.valueChanged.connect(self.sizeChanged)

        self.model = Model(self, node.imgchannels)
        self.w.tableView.setModel(self.model)
        self.model.changed.connect(self.chansChanged)
        self.w.tableView.setItemDelegateForColumn(4, ComboBoxDelegate(self.model, MODES))
        self.w.tableView.setColumnWidth(0, 15)
        self.w.tableView.setColumnWidth(1, 25)
        self.w.tableView.setColumnWidth(2, 25)
        self.w.tableView.setColumnWidth(3, 25)
        self.w.tableView.setColumnWidth(4, 40)
        self.nodeChanged()

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
