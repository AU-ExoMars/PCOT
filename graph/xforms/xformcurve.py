from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas,ui.mplwidget
from xform import singleton,XFormType

# number of points in lookup table
NUMPOINTS=100
# x-coords of table
lutxcoords = np.linspace(0,255,NUMPOINTS)

class TabCurve(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabcurve.ui') # same UI as sink
        self.canvas = self.getUI(ui.canvas.Canvas,'canvas')
        self.addDial = self.getUI(QtWidgets.QDial,'addDial')
        self.mulDial = self.getUI(QtWidgets.QDial,'mulDial')
        self.addDial.valueChanged.connect(self.setAdd)
        self.mulDial.valueChanged.connect(self.setMul)
        self.mpl = self.getUI(ui.mplwidget.MplWidget,'figure')
        self.plot = None # the matplotlib plot which we update
        # sync tab with node
        self.onNodeChanged()

    def setAdd(self,v):
        # when a control changes, update node and perform
        self.node.add = (v-50)*10
        self.node.perform()
    def setMul(self,v):
        # when a control changes, update node and perform
        self.node.mul = v/10
        self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.addDial.setValue(self.node.add/10+50)
        self.mulDial.setValue(self.node.mul*10)
        self.node.type.genLut(self.node) # yeah, ugly.
        if self.plot is None:
            # set up the initial plot
            # doing stuff without pyplot is weird!
            self.mpl.ax.set_xlim(0,255)
            self.mpl.ax.set_ylim(0,255)
            # make the plot, store the zeroth plot (ours)
            self.plot=self.mpl.ax.plot(lutxcoords,self.node.lut,'r')[0]
        else:
            self.plot.set_ydata(self.node.lut)
        self.mpl.canvas.draw() # present drawing

        # display image        
        self.canvas.display(self.node.img)


class XformCurveBase(XFormType):
    def __init__(self,name,conntype):
        super().__init__(name)
        self.addInputConnector("in",conntype)
        self.addOutputConnector("out",conntype)
        
    def createTab(self,mainui,n):
        return TabCurve(mainui,n)
        
    def init(self,node):
        node.img = None
        node.add = 0
        node.mul = 1
        self.genLut(node)
        
    def genLut(self,node):
        # generate the LUT
        xb = (node.mul*(lutxcoords-127)+node.add)/255
        node.lut = (255/(1+np.exp(-xb))).astype(np.ubyte)
    

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            node.img = np.interp(img,lutxcoords,node.lut).astype(np.ubyte)
            print(node.img.shape)

        node.setOutput(0,node.img)


@singleton
class XformCurveRGB(XformCurveBase):
    def __init__(self):
        super().__init__('curveRGB','img888')

@singleton
class XformCurveGrey(XformCurveBase):
    def __init__(self):
        super().__init__('curvegrey','imggrey')
        

