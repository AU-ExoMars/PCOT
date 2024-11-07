import math

import numpy as np
from PySide2.QtGui import QDoubleValidator

from pcot import ui
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XFormException


# This dict is a map from values in the test function combo box to the actual shorthand names ussed
# by the parameters

TEST_COMBO_NAMES_TO_SHORT_NAMES = {
    'Less than or equal to': 'le',
    'Greater than or equal to': 'ge',
    'Greater than': 'gt',
    'Less than': 'lt',
    'ALWAYS': 'always'
}
# the inverse map
SHORT_NAMES_TO_TEST_COMBO_NAMES = {v: k for k, v in TEST_COMBO_NAMES_TO_SHORT_NAMES.items()}


@xformtype
class XFormDQMod(XFormType):
    """
    Modify DQ bits based on conditions in the existing nominal or uncertainty for all bands
    or just a single band.

    <blockquote style="background-color: #ffd0d0;">
    **WARNING**: This may set "bad" bits which will be masked in any calculation. For some settings,
    these bad bits can mask bands other than those from which they are derived. Calculations involving
    pixels with these bits will be partially derived from the mask, but this information will not
    be tracked by the source mechanism. This means that some source tracking information
    can be lost. (Issue #69)
    </blockquote>
    """

    def __init__(self):
        super().__init__("dqmod", "utility", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

        self.params = TaggedDictType(
            val=("Value to test against", float, 0.0),
            dq=("DQ bits to set", int, 0),
            mod=("Set or clear bits", str, 'set', ['set', 'clear']),
            test=("Test to perform", str, "le", list(TEST_COMBO_NAMES_TO_SHORT_NAMES.values())),
            data=("Data to test", str, 'nominal', ['nominal', 'uncertainty']),
            band=("Band to test (or None for all)", Maybe(int), None)
        )

    def init(self, node):
        pass

    def createTab(self, xform, window):
        return TabDQMod(xform, window)

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        params = node.params
        if img is not None:
            img = img.copy()
            if params.band is not None and not (0 <= params.band < img.channels):
                params.band = 0
            # get the part of the image we're working on (due to ROIs, etc)
            subimg = img.subimage()
            fulldq = subimg.dq.copy()  # this is the data we'll change
            # get the data we are testing against
            d = subimg.img if params.data == 'nominal' else subimg.uncertainty
            if params.band is not None:
                # we're working on just one band, so slice into the arrays to get only the relevant data.
                # We need to keep hold of that fulldq array because that's what we use to replace the old
                # data in modifyWithSub
                if len(d.shape) == 2:
                    # if it's a single band image the shape will be (h,w), so we don't need to get the band out.
                    dq = fulldq
                else:
                    # but we do need to if the shape has 3 elements.
                    dq = fulldq[:, :, params.band]
                    d = d[:, :, params.band]
            else:
                dq = fulldq

            # now do the test, modifying the DQ accordingly.
            if params.test == 'le':
                bitsToChange = np.where(d <= params.val, params.dq, 0).astype(np.uint16)
            elif params.test == 'ge':
                bitsToChange = np.where(d >= params.val, params.dq, 0).astype(np.uint16)
            elif params.test == 'gt':
                bitsToChange = np.where(d > params.val, params.dq, 0).astype(np.uint16)
            elif params.test == 'lt':
                bitsToChange = np.where(d < params.val, params.dq, 0).astype(np.uint16)
            elif params.test == 'always':
                bitsToChange = np.uint16(params.dq)
            else:
                raise XFormException("CTRL", f"Unknown test in dqmod {params.test}")

            if params.mod == 'set':
                dq |= bitsToChange
            else:
                dq &= ~bitsToChange

            # put the data back in, preserving the uncertainty and not setting the NOUNC bit.
            img = img.modifyWithSub(subimg, None, dqv=fulldq, uncertainty=subimg.uncertainty)
        else:
            params.band = None

        node.setOutput(0, Datum(Datum.IMG, img))


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
        params = self.node.params
        with SignalBlocker(self.w.bandCombo):
            self.w.bandCombo.clear()
            self.w.bandCombo.addItem('All')
            img = self.node.getOutput(0, Datum.IMG)
            if img is not None:
                self.w.bandCombo.addItems([str(x) for x in range(0, img.channels)])
                self.w.bandCombo.setCurrentText("All")
                if params.band is None:
                    self.w.bandCombo.setCurrentText("All")
                else:
                    self.w.bandCombo.setCurrentText(str(params.band))
            else:
                self.w.bandCombo.setCurrentText("All")

        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.getOutput(0))

        if not self.dontSetText:
            self.w.dataCombo.setCurrentText(params.data)
            self.w.testCombo.setCurrentText(params.test)
            self.w.modCombo.setCurrentText(params.mod)
            self.w.testEdit.setText(str(params.val))
        self.w.dqbits.bits = params.dq
        self.w.dqbits.setChecksToBits()

    def DQChanged(self):
        self.mark()
        self.node.params.dq = self.w.dqbits.bits
        self.changed()

    def modChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.params.mod = s
        self.dontSetText = False
        self.changed()

    def testChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.params.test = TEST_COMBO_NAMES_TO_SHORT_NAMES[s]
        self.dontSetText = False
        self.changed()

    def dataChanged(self, s):
        self.mark()
        self.dontSetText = True
        self.node.params.data = s
        self.dontSetText = False
        self.changed()

    def bandChanged(self, s):
        self.mark()
        self.dontSetText = True
        if s == 'All':
            self.node.params.band = None
        else:
            self.node.params.band = int(s)
        self.dontSetText = False
        self.changed()

    def testEditChanged(self, t):
        v = 0 if t == '' else float(t)
        self.mark()
        self.node.params.val = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False
