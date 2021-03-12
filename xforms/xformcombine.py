from functools import partial

import numpy as np
from PyQt5.QtWidgets import QGridLayout, QComboBox, QLabel

import ui
from channelsource import IChannelSource
from xform import xformtype, XFormType

NUMCHANS = 6


@xformtype
class XFormCombine(XFormType):
    def __init__(self):
        super().__init__("combine", "maths", "0.0.0")
        for x in range(0, NUMCHANS):
            self.addInputConnector(str(x), "img")
        self.addOutputConnector("", "img")
        self.autoserialise = ()

    def createTab(self, n, w):
        return TabCombine(n, w)

    def init(self, node):
        node.img = None
        node.op1chan = [0] * NUMCHANS
        node.operators = [0] * NUMCHANS
        node.op2chan = [0] * NUMCHANS

    def perform(self, node):
        # this is a list, for each image, of a list of channels.
        node.imgChannelStrings = []

        # populate channel list for combo boxes, for later.
        # We also look at the operators to work out the size of the output
        maxchan = 0
        # work out max size too
        w, h = 0, 0
        for i in range(NUMCHANS):
            inp = node.getInput(i)
            if inp is not None:
                # there's an image, grand. We have to populate a list for each image, so it's there for the
                # combo boxes later.
                chanStringList = [IChannelSource.stringForSet(s, node.graph.captionType) for s in inp.sources]
                node.imgChannelStrings.append(chanStringList)
                if inp.w > w:
                    w = inp.w
                if inp.h > h:
                    h = inp.h
            else:
                node.imgChannelStrings.append([])
            if node.operators[i] > 0:
                maxchan = i

        # we're doing nowt
        if maxchan == 0:
            out = None
        else:
            # prepare a zeroes array
            zeroes = np.zeros((h,w))
            # for each channel..
            for i in range(NUMCHANS):
                idx1 = node.op1chan[i]
                idx2 = node.op2chan[i]
                op = node.operators[i]
                ## TODO this is fucking horrible, because the data in op1chan/op2chan is just indices...
                ## the actual data is in the item attached to the combo box as (imgidx,chan) tuples. Hm.
#                if idx1 != 0:
#                    img1 = extractChannel(node,)



def shortLab(s):
    ll = QLabel(s)
    ll.setMaximumHeight(20)
    return ll


class TabCombine(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabcombine.ui')
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)

        # create all the rows
        gridLayout = QGridLayout()
        self.w.widget.setLayout(gridLayout)

        gridLayout.addWidget(shortLab("input 1"), 0, 1)
        gridLayout.addWidget(shortLab("operator"), 0, 2)
        gridLayout.addWidget(shortLab("input 2"), 0, 3)

        self.op1widgets = []
        self.op2widgets = []
        self.operatorWidgets = []

        for inp in range(0, NUMCHANS):
            gridLayout.addWidget(shortLab("Ch. {}".format(inp)), inp + 1, 0)

            w = QComboBox()
            w.currentIndexChanged.connect(partial(self.op1changed, inp))
            self.op1widgets.append(w)
            gridLayout.addWidget(w, inp + 1, 1)

            w = QComboBox()
            w.addItem("ZERO")
            w.addItem("add")
            w.addItem("subtract")
            w.addItem("multiply")
            w.currentIndexChanged.connect(partial(self.operatorChanged, inp))
            self.operatorWidgets.append(w)
            gridLayout.addWidget(w, inp + 1, 2)

            w = QComboBox()
            w.currentIndexChanged.connect(partial(self.op2changed, inp))
            self.op2widgets.append(w)
            gridLayout.addWidget(w, inp + 1, 3)

        # sync tab with node
        self.onNodeChanged()

    def op1changed(self, inp):
        self.node.op1chan[inp] = self.op1widgets[inp].currentIndex()
        self.changed()

    def op2changed(self, inp):
        self.node.op2chan[inp] = self.op2widgets[inp].currentIndex()
        self.changed()

    def operatorChanged(self, inp):
        self.node.operators[inp] = self.operatorWidgets[inp].currentIndex()
        self.changed()

    def initComboFromChannels(self, combos):
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            # always add ZERO
            combo.addItem("ZERO", (-1, -1))
            # now add the channels for the image (if any)
            for imgIdx in range(len(self.node.imgChannelStrings)):
                lst = self.node.imgChannelStrings[imgIdx]
                for chan in range(len(lst)):
                    combo.addItem("{}: {}".format(imgIdx, lst[chan]), (imgIdx, chan))
            combo.blockSignals(False)

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.initComboFromChannels(self.op1widgets)
        self.initComboFromChannels(self.op2widgets)

        rePerform = False

        # we have to update the widgets from the node, which causes recursion if setCurrentIndex runs.
        # So we block signals.
        for i in range(0, NUMCHANS):
            self.op1widgets[i].blockSignals(True)
            self.op2widgets[i].blockSignals(True)
            self.operatorWidgets[i].blockSignals(True)

            # All this boilerplate (yes, should be DRY but isn't) is doing is
            # checking to see if the channel selections are still valid. If not, we set
            # to zero and flag that we need the reperform the node. That should fix it.

            idx = self.node.op1chan[i]
            if idx >= self.op1widgets[i].count():
                idx = 0
                self.node.op1chan[i] = idx
                rePerform = True
            self.op1widgets[i].setCurrentIndex(idx)

            idx = self.node.op2chan[i]
            if idx >= self.op2widgets[i].count():
                idx = 0
                self.node.op2chan[i] = idx
                rePerform = True
            self.op2widgets[i].setCurrentIndex(idx)

            self.operatorWidgets[i].setCurrentIndex(self.node.operators[i])

            self.op1widgets[i].blockSignals(False)
            self.op2widgets[i].blockSignals(False)
            self.operatorWidgets[i].blockSignals(False)

        if rePerform:
            self.changed()
        self.w.canvas.display(self.node.img)
