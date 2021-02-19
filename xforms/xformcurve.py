from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas, ui.mplwidget
from xform import xformtype, XFormType
from pancamimage import ImageCube

# number of points in lookup table
NUMPOINTS = 1000
# x-coords of table
lutxcoords = np.linspace(0, 1, NUMPOINTS)


def curve(img, mask, node):
    masked = np.ma.masked_array(img, mask=~mask)
    cp = img.copy()
    np.putmask(cp, mask, np.interp(masked, lutxcoords, node.lut).astype(np.float32))
    return cp


@xformtype
class XformCurve(XFormType):
    """Maps the image channel intensities to a curve. Honours regions of interest."""

    def __init__(self):
        super().__init__("curve", "processing", "0.0.0")
        self.addInputConnector("", "img")  # accept any image
        self.addOutputConnector("", "img")  # produce any image, but will change on input connect
        self.autoserialise = ('add', 'mul')
        self.hasEnable = True

    def createTab(self, n, w):
        return TabCurve(n, w)

    # this xform can take different image types, but doing so changes
    # the output types, overriding the generic one given in the constructor.
    # This is called to make that happen if an input type (i.e. the type of the
    # output connected to the input) changes.
    def generateOutputTypes(self, node):
        node.matchOutputsToInputs([(0, 0)])

    def init(self, node):
        node.img = None
        node.add = 0
        node.mul = 1

    def recalculate(self, node):
        print("RECALC")
        # recalculate the LUT each time - need to get recalculate() working
        xb = node.mul * (lutxcoords - 0.5) + node.add
        node.lut = (1.0 / (1.0 + np.exp(-xb)))

    # given a dictionary, set the values in the node from the dictionary    
    def perform(self, node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        elif not node.enabled:
            node.img = img
            node.img.setMapping(node.mapping)
        else:
            subimage = img.subimage()

            if img.channels == 1:
                newsubimg = curve(subimage.img, subimage.mask, node)
            else:
                # TODO won't work on non-RGB
                newsubimg = cv.merge([curve(x, subimage.mask, node) for x in cv.split(subimage.img)])
            node.img = img.modifyWithSub(subimage, newsubimg)
            node.img.setMapping(node.mapping)
        node.setOutput(0, node.img)


class TabCurve(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabcurve.ui')
        self.w.addDial.valueChanged.connect(self.setAdd)
        self.w.mulDial.valueChanged.connect(self.setMul)
        self.w.canvas.setMapping(node.mapping)
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
        self.node.type.recalculate(self.node)
        if self.plot is None:
            # set up the initial plot
            # doing stuff without pyplot is weird!
            self.w.mpl.ax.set_xlim(0, 1)
            self.w.mpl.ax.set_ylim(0, 1)
            # make the plot, store the zeroth plot (ours)
            self.plot = self.w.mpl.ax.plot(lutxcoords, self.node.lut, 'r')[0]
        else:
            self.plot.set_ydata(self.node.lut)
        self.w.mpl.canvas.draw()  # present drawing

        # display image        
        self.w.canvas.display(self.node.img)
