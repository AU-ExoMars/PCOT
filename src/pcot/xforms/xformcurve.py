import cv2 as cv
import numpy as np

import pcot.conntypes as conntypes
import pcot.operations as operations
import pcot.ui.tabs
from pcot.operations.curve import curve, genLut, lutxcoords
from pcot.xform import xformtype, XFormType


@xformtype
class XformCurve(XFormType):
    """
    Maps the image channel intensities to a logistic sigmoid curve, y=1/(1+e^-(ax+b)), where a is "mul" and b is "add".
    Honours regions of interest."""

    def __init__(self):
        super().__init__("curve", "processing", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("", conntypes.IMG)
        self.autoserialise = ('add', 'mul')
        self.hasEnable = True

    def createTab(self, n, w):
        return TabCurve(n, w)

    def init(self, node):
        node.img = None
        node.add = 0
        node.mul = 1

    def perform(self, node):
        operations.performOp(node, operations.curve.curve, add=node.add, mul=node.mul)


class TabCurve(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcurve.ui')
        self.w.addDial.valueChanged.connect(self.setAdd)
        self.w.mulDial.valueChanged.connect(self.setMul)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setPersister(node)

        self.plot = None  # the matplotlib plot which we update
        # sync tab with node
        self.onNodeChanged()

    def setAdd(self, v):
        # when a control changes, update node and perform
        self.node.add = (v - 50) * 0.1
        self.changed()

    def setMul(self, v):
        # when a control changes, update node and perform
        self.node.mul = v / 10
        self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.addDial.setValue(self.node.add * 10 + 50)
        self.w.mulDial.setValue(self.node.mul * 10)
        lut = genLut(self.node.mul, self.node.add)
        if self.plot is None:
            # set up the initial plot
            # doing stuff without pyplot is weird!
            self.w.mpl.ax.set_xlim(0, 1)
            self.w.mpl.ax.set_ylim(0, 1)
            # make the plot, store the zeroth plot (ours)

            self.plot = self.w.mpl.ax.plot(lutxcoords, lut, 'r')[0]
        else:
            self.plot.set_ydata(lut)
        self.w.mpl.canvas.draw()  # present drawing

        # display image        
        self.w.canvas.display(self.node.img)
