import math

import numpy as np
from PySide2.QtGui import QDoubleValidator

from pcot import ui
from pcot.datum import Datum
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XFormException


@xformtype
class XFormDQMod(XFormType):
    """Modify DQ bits based on conditions in the existing nominal or uncertainty for all bands
    or just a single band."""

    def __init__(self):
        super().__init__("dqmod", "utility", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('val', 'dq', 'mod', 'test', 'data', 'band')

    def init(self, node):
        node.val = 0
        node.dq = 0
        node.mod = 'Set'
        node.test = "Less than or equal to"
        node.data = 'Nominal'
        node.band = None

    def createTab(self, xform, window):
        return TabDQMod(xform, window)

    def perform(self, node):
        if node.val is None:
            node.val = 0.0
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            img = img.copy()
            if node.band is not None and not (0 <= node.band < img.channels):
                node.band = None
            # get the part of the image we're working on (due to ROIs, etc)
            subimg = img.subimage()
            fulldq = subimg.dq.copy()  # this is the data we'll change
            # get the data we are testing against
            d = subimg.img if node.data == 'Nominal' else subimg.uncertainty
            if node.band is not None:
                # we're working on just one band, so slice into the arrays to get only the relevant data.
                # We need to keep hold of that fulldq array because that's what we use to replace the old
                # data in modifyWithSub
                if len(d.shape) == 2:
                    # if it's a single band image the shape will be (h,w), so we don't need to get the band out.
                    dq = fulldq
                else:
                    # but we do need to if the shape has 3 elements.
                    dq = fulldq[:, :, node.band]
                    d = d[:, :, node.band]
            else:
                dq = fulldq

            # now do the test, modifying the DQ accordingly.
            if node.test == 'Less than or equal to':
                bitsToChange = np.where(d <= node.val, node.dq, 0).astype(np.uint16)
            else:
                bitsToChange = np.where(d >= node.val, node.dq, 0).astype(np.uint16)

            if node.mod == 'Set':
                dq |= bitsToChange
            else:
                dq &= ~bitsToChange

            # put the data back in, preserving the uncertainty and not setting the NOUNC bit.
            img = img.modifyWithSub(subimg, None, dqv=fulldq, uncertainty=subimg.uncertainty)
        else:
            node.band = None

        node.img = img
        node.out = Datum(Datum.IMG, img)
        node.setOutput(0, node.out)


class TabDQMod(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabdqmod.ui')

        self.w.testEdit.setValidator(QDoubleValidator(-math.inf, math.inf, -1, w))
        self.w.dqbits.changed.connect(self.DQChanged)
        self.w.modCombo.currentTextChanged.connect(self.modChanged)
        self.w.bandCombo.currentTextChanged.connect(self.bandChanged)
        self.w.dataCombo.currentTextChanged.connect(self.dataChanged)
        self.w.testCombo.currentTextChanged.connect(self.testChanged)
        self.w.testEdit.textChanged.connect(self.testEditChanged)
        self.dontSetText = False
        self.nodeChanged()

    def onNodeChanged(self):
        with SignalBlocker(self.w.bandCombo):
            self.w.bandCombo.clear()
            self.w.bandCombo.addItem('All')
            if self.node.img is not None:
                self.w.bandCombo.addItems([str(x) for x in range(0, self.node.img.channels)])
                self.w.bandCombo.setCurrentText("All")
                if self.node.band is None:
                    self.w.bandCombo.setCurrentText("All")
                else:
                    self.w.bandCombo.setCurrentText(str(self.node.band))
            else:
                self.w.bandCombo.setCurrentText("All")

        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.display(self.node.img)

        if not self.dontSetText:
            self.w.dataCombo.setCurrentText(self.node.data)
            self.w.testCombo.setCurrentText(self.node.test)
            self.w.modCombo.setCurrentText(self.node.mod)
            self.w.testEdit.setText(str(self.node.val))
        self.w.dqbits.bits = self.node.dq
        self.w.dqbits.setChecksToBits()

    def DQChanged(self):
        self.mark()
        self.node.dq = self.w.dqbits.bits
        self.changed()

    def modChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.mod = s
        self.dontSetText = False
        self.changed()

    def testChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.test = s
        self.dontSetText = False
        self.changed()

    def dataChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.data = s
        self.dontSetText = False
        self.changed()

    def bandChanged(self, s):
        self.mark()
        self.dontSetText = True
        if s == 'All':
            self.node.band = None
        else:
            self.node.band = int(s)
        self.dontSetText = False
        self.changed()

    def testEditChanged(self, t):
        v = 0 if t == '' else float(t)
        self.mark()
        self.node.val = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False
