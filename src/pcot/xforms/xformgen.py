import dataclasses
import logging
from dataclasses import dataclass
from typing import Any, List

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import QModelIndex
from PySide2.QtWidgets import QMessageBox

import cv2 as cv

import pcot.ui.tabs
from pcot import ui
from pcot.datum import Datum
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource, FilterOnlySource
from pcot.ui.tablemodel import TableModel, ComboBoxDelegate
from pcot.utils import SignalBlocker
from pcot.xform import xformtype, XFormType, XFormException

DEFAULTSIZE = 256
MODES = ['flat', 'ripple-n', 'ripple-u', 'ripple-un', 'half', 'checkx', 'checky', 'rand']
DEFAULTMODE = 'flat'

logger = logging.getLogger(__name__)


@dataclass
class ChannelData:
    """These are the items stored in the array we generate the image from: one for each band"""
    n: float = 0.0  # nominal value, used as multiplier for sine wave in ripple-n and ripple-un
    u: float = 0.0  # uncertainty of value, used as multiplier for sine wave in ripple-n and ripple-un
    cwl: int = 100  # centre wavelength
    mode: str = 'flat'  # mode - see node description

    # text info

    text: str = ''
    textx: int = 0
    texty: int = 0
    textsize: float = 1       # some factor of img size

    @staticmethod
    def getHeader():
        return ['N', 'U', 'CWL', 'mode', 'text', 'textx', 'texty', 'textsize']  # headers

    def serialise(self):
        return dataclasses.asdict(self)

    @staticmethod
    def deserialise(t):
        if isinstance(t, dict):
            return ChannelData(**t)
        else:
            return ChannelData(*t)


@xformtype
class XFormGen(XFormType):
    """
    Generate an image with given channel values. Can also generate patterns. Each band is given a nominal value
    and uncertainty, along with a centre frequency and a mode (for patterns).

    Modes are:

    * flat : N and U are used to fill the entire band
    * ripple-n: the N value is not a value, but a multiplier applied to distance from centre - the sine of this
    gives the value. The U value is generated as in 'flat'
    * ripple-u: as ripple-n, but this time U is used as a multiplier to generate the ripple pattern in uncertainty,
    while N is generated as in 'flat'
    * ripple-un: both values are ripple multipliers.
    * half: nominal is N on the left, U on the right. Uncertainty is 0.1. (Test value)
    * checkx: nominal is a checquered pattern with each square of size N, offset by U in the x-axis. uncertainty=nominal.
    * checky: nominal is a checquered pattern with each square of size N, offset by U in the y-axis. uncertainty=nominal.
    * rand: both nom. and unc. are filled with non-negative pseudorandom noise multiplied by N and U respectively

    A useful pattern might be something like this:

    *   Chan 0:         checkx, N=8, U=0
    *   Chan 1:         checkx, N=8, U=4
    *   Chan 2:         checky, N=8, U=4

    To get variation in uncertainty, create a similar pattern but with a longer period using another gen node:

    *   Chan 0:         checkx, N=16, U=0
    *   Chan 1:         checkx, N=16, U=8
    *   Chan 2:         checky, N=16, U=8

    and merge the two together, using the first gen to create nominal values and the second to create uncertainty values,
    with an expr node using the expression **v(a,b)**.
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

        listOfCwls = [x.cwl for x in node.imgchannels]
        if len(listOfCwls) != len(set(listOfCwls)):
            node.setError(XFormException('GEN', "DUPLICATE CWLS"))

        for chan in node.imgchannels:
            if chan.mode == 'flat':
                # flat mode is easy
                n = np.full((node.imgheight, node.imgwidth), chan.n)
                u = np.full((node.imgheight, node.imgwidth), chan.u)
            elif chan.mode == 'ripple-n':
                # we build an expression based on position to get a ripple pattern in n
                n = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                n = np.sin(n) * 0.5 + 0.5
                # but u remains flat
                u = np.full((node.imgheight, node.imgwidth), chan.u)
            elif chan.mode == 'ripple-u':
                # as above, but the other way around
                n = np.full((node.imgheight, node.imgwidth), chan.n)
                u = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                u = np.sin(u) * 0.5 + 0.5
            elif chan.mode == 'ripple-un':
                # two ripples
                n = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                n = np.sin(n) * 0.5 + 0.5
                u = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                u = np.sin(u) * 0.5 + 0.5
            elif chan.mode == 'half':
                n = np.where(x<node.imgwidth/2, chan.n, chan.u)
                u = np.full((node.imgheight, node.imgwidth), 0.1)
            elif chan.mode == 'checkx':
                y, x = np.indices((node.imgheight, node.imgwidth))
                n = ((np.array((y, x+chan.u))//chan.n).sum(axis=0) % 2).astype(np.float32)
                u = n
            elif chan.mode == 'checky':
                y, x = np.indices((node.imgheight, node.imgwidth))
                n = ((np.array((y+chan.u, x))//chan.n).sum(axis=0) % 2).astype(np.float32)
                u = n
            elif chan.mode == 'rand':
                rngN = np.random.default_rng(seed=int(chan.n*10000))
                rngU = np.random.default_rng(seed=int(chan.u*10000))
                n = rngN.random((node.imgheight, node.imgwidth), np.float32)
                u = rngN.random((node.imgheight, node.imgwidth), np.float32)
            else:
                raise XFormException('INTR', "bad mode in gen")

            # write text
            if chan.text != '':
                fontsize = node.imgheight * chan.textsize * 0.007
                thickness = int(fontsize*3)
                (w, h), baseline = cv.getTextSize(chan.text, cv.FONT_HERSHEY_SIMPLEX,
                                                  fontScale=fontsize, thickness=thickness)

                cv.putText(n, chan.text, (chan.textx, chan.texty+h), cv.FONT_HERSHEY_SIMPLEX,
                           color=1,
                           fontScale=fontsize, lineType=1, thickness=thickness)

            ns.append(n)
            us.append(u)

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


class GenModel(TableModel):
    """This is the model which acts between the list of ChannelData items and the table view."""

    def __init__(self, tab, _data: List[ChannelData]):
        super().__init__(tab, ChannelData, _data, True)

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview or any item delegates"""
        if index.isValid():
            self.tab.mark()  # we do the undo mark here, before the data is changed
            field = index.row()
            item = index.column()
            d = self.d[item]

            try:
                if field == 0:
                    d.n = float(value)
                elif field == 1:
                    d.u = float(value)
                elif field == 2:
                    value = int(value)
                    if value >= 0:
                        d.cwl = value
                    else:
                        return False
                elif field == 3:
                    d.mode = value
                elif field == 4:
                    d.text = value
                elif field == 5:
                    d.textx = int(value)
                elif field == 6:
                    d.texty = int(value)
                elif field == 7:
                    d.textsize = float(value)

                # tell the view we changed
                self.dataChanged.emit(index, index, (QtCore.Qt.DisplayRole,))
                # and tell any other things too (such as the tab!)
                self.changed.emit()
            except ValueError:
                ui.log("Bad value type when setting data in GenModel")
            return True
        return False


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

        self.w.splitter.setSizes([1000, 2000])   # 1:2 ratio between table and canvas

        self.model = GenModel(self, node.imgchannels)
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
            if QMessageBox.question(self.window, "Delete channel", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
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
