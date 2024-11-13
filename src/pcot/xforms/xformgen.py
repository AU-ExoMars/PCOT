import logging

import numpy as np
from PySide2.QtWidgets import QMessageBox

import cv2 as cv

import pcot.ui.tabs
from pcot import ui
from pcot.datum import Datum
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType
from pcot.sources import MultiBandSource, Source, StringExternal
from pcot.ui.tablemodel import ComboBoxDelegate, TableModelTaggedAggregate
from pcot.utils import SignalBlocker
from pcot.utils.image import generate_gradient
from pcot.xform import xformtype, XFormType, XFormException

DEFAULTSIZE = 256
MODES = ['flat', 'ripple-n', 'ripple-u', 'ripple-un', 'half', 'checkx', 'checky', 'rand', 'gaussian',
         'gradient-x', 'gradient-y']
DEFAULTMODE = 'flat'

logger = logging.getLogger(__name__)

TAGGEDDICTCHANNEL = TaggedDictType(
    n=("Nominal control value - 'mode' determines how it is used", float, 0.0),
    u=("Uncertainty control value - 'mode' determines how it is used", float, 0.0),
    cwl=("Centre wavelength", int, 100),
    mode=("Mode of operation", str, DEFAULTMODE, MODES),
    text=("Text to write on the image", str, ""),
    textx=("X position of text", int, 0),
    texty=("Y position of text", int, 0),
    textsize=("Size of text (units arbitrary but relative to image size) ", float, 1.0)
).setOrdered()

TAGGEDDICT = TaggedDictType(
    imgwidth=("Width of the image", int, DEFAULTSIZE),
    imgheight=("Height of the image", int, DEFAULTSIZE),
    chans=("Data for each channel", TaggedListType("Channel data", TAGGEDDICTCHANNEL, 0))
)



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
    * rand: both nom. and unc. are filled with non-negative pseudorandom uniform noise multiplied by N and U respectively
    * gaussian: nom. is filled with gaussian noise centered around N with a std. dev. of U. U is zero. The RNG is seeded
        from the CWL.
    * gradient-x: nom. is filled with a gradient from 0-1, U is zero. Number of steps is N (zero means smooth).
    * gradient-y: nom. is filled with a gradient from 0-1, U is zero. Number of steps is N (zero means smooth).

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
        self.params = TAGGEDDICT

    def createTab(self, n, w):
        return TabGen(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        # we'll fill these lists with data for the image bands nominal and uncertainty values
        ns = []
        us = []

        w = node.params.imgwidth
        h = node.params.imgheight
        # build a meshgrid so we can make calculations based on position
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        cx = w / 2.0
        cy = h / 2.0

        listOfCwls = [x.cwl for x in node.params.chans]
        if len(listOfCwls) != len(set(listOfCwls)):
            node.setError(XFormException('GEN', "DUPLICATE CWLS"))

        for chan in node.params.chans:
            if chan.mode == 'flat':
                # flat mode is easy
                n = np.full((h, w), chan.n)
                u = np.full((h, w), chan.u)
            elif chan.mode == 'ripple-n':
                # we build an expression based on position to get a ripple pattern in n
                n = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                n = np.sin(n) * 0.5 + 0.5
                # but u remains flat
                u = np.full((h, w), chan.u)
            elif chan.mode == 'ripple-u':
                # as above, but the other way around
                n = np.full((h, w), chan.n)
                u = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                u = np.sin(u) * 0.5 + 0.5
            elif chan.mode == 'ripple-un':
                # two ripples
                n = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.n
                n = np.sin(n) * 0.5 + 0.5
                u = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * chan.u
                u = np.sin(u) * 0.5 + 0.5
            elif chan.mode == 'half':
                n = np.where(x < w / 2, chan.n, chan.u)
                u = np.full((h, w), 0.1)
            elif chan.mode == 'checkx':
                y, x = np.indices((h, w))
                n = ((np.array((y, x + chan.u)) // chan.n).sum(axis=0) % 2).astype(np.float32)
                u = n
            elif chan.mode == 'checky':
                y, x = np.indices((h, w))
                n = ((np.array((y + chan.u, x)) // chan.n).sum(axis=0) % 2).astype(np.float32)
                u = n
            elif chan.mode == 'rand':
                rngN = np.random.default_rng(seed=int(chan.n * 10000))
                rngU = np.random.default_rng(seed=int(chan.u * 10000))
                n = rngN.random((h, w), np.float32)
                u = rngN.random((h, w), np.float32)
            elif chan.mode == 'gaussian':
                rng = np.random.default_rng(seed=chan.cwl)
                n = rng.normal(chan.n, chan.u, (h, w))
                u = np.zeros((h, w))
            elif chan.mode == 'gradient-x':
                n = generate_gradient(w, h, True, chan.n)
                u = np.zeros((h, w))
            elif chan.mode == 'gradient-y':
                n = generate_gradient(w, h, False, chan.n)
                u = np.zeros((h, w))

            else:
                raise XFormException('INTR', "bad mode in gen")

            # write text
            if chan.text != '':
                fontsize = h * chan.textsize * 0.007
                thickness = int(fontsize * 3)
                (tw, th), baseline = cv.getTextSize(chan.text, cv.FONT_HERSHEY_SIMPLEX,
                                                  fontScale=fontsize, thickness=thickness)

                cv.putText(n, chan.text, (chan.textx, chan.texty + th), cv.FONT_HERSHEY_SIMPLEX,
                           color=1,
                           fontScale=fontsize, lineType=1, thickness=thickness)

            ns.append(n)
            us.append(u)

        # build the image arrays
        if len(ns) > 0:
            ns = np.dstack(ns).astype(np.float32)
            us = np.dstack(us).astype(np.float32)

            # construct Filter only sources - these don't have input data but do have a filter.
            sources = [Source().setBand(Filter(chan.cwl, 30, 1.0, idx=i))
                            .setExternal(StringExternal("gen", node.displayName))
                       for i, chan in enumerate(node.params.chans)]
            # make and output the image
            img = ImageCube(ns, node.mapping, uncertainty=us, sources=MultiBandSource(sources))
            node.setOutput(0, Datum(Datum.IMG, img))
        else:
            node.setOutput(0, Datum.null)


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

        self.w.splitter.setSizes([1000, 2000])  # 1:2 ratio between table and canvas

        self.model = TableModelTaggedAggregate(self, node.params.chans, True)
        self.w.tableView.setModel(self.model)
        self.model.changed.connect(self.chansChanged)
        self.w.tableView.setItemDelegateForRow(3, ComboBoxDelegate(self.w.tableView, self.model, MODES))
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
        self.node.params.imgwidth = self.w.spinWidth.value()
        self.node.params.imgheight = self.w.spinHeight.value()
        self.changed()

    def chansChanged(self):
        # we don't need to mark or set data here, it's already been done in the model!
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)

        with SignalBlocker(self.w.spinWidth, self.w.spinHeight):
            self.w.spinWidth.setValue(self.node.params.imgwidth)
            self.w.spinHeight.setValue(self.node.params.imgheight)

        self.w.canvas.display(self.node.getOutput(0))
