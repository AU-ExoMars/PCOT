from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.mplwidget
from xform import xformtype,XFormType
from pancamimage import Image

# number of points in lookup table
NUMPOINTS=100
# x-coords of table
lutxcoords = np.linspace(0,255,NUMPOINTS)

@xformtype
class XformCurve(XFormType):
    def __init__(self):
        super().__init__("curve","0.0.0")
        self.addInputConnector("","img") # accept any image
        self.addOutputConnector("","img") # produce any image, but will change on input connect
        self.autoserialise=('add','mul')
        
    def createTab(self,n):
        return TabCurve(n)

    # this xform can take different image types, but doing so changes
    # the output types, overriding the generic one given in the constructor.
    # This is called to make that happen if an input type (i.e. the type of the
    # output connected to the input) changes.
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])
    
    def init(self,node):
        node.img = None
        node.add = 0
        node.mul = 1
        self.recalculate(node)
        
    def recalculate(self,node):
        # generate the LUT
        xb = (node.mul*(lutxcoords-127)+node.add)/255
        node.lut = (255/(1+np.exp(-xb))).astype(np.ubyte)
        
    # given a dictionary, set the values in the node from the dictionary    
    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            node.img = Image(np.interp(img.img,lutxcoords,node.lut).astype(np.ubyte))

        node.setOutput(0,node.img)


class TabCurve(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabcurve.ui') # same UI as sink
        self.w.addDial.valueChanged.connect(self.setAdd)
        self.w.mulDial.valueChanged.connect(self.setMul)
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
        self.w.addDial.setValue(self.node.add/10+50)
        self.w.mulDial.setValue(self.node.mul*10)
        self.node.type.recalculate(self.node) # have to rebuild LUT
        if self.plot is None:
            # set up the initial plot
            # doing stuff without pyplot is weird!
            self.w.mpl.ax.set_xlim(0,255)
            self.w.mpl.ax.set_ylim(0,255)
            # make the plot, store the zeroth plot (ours)
            self.plot=self.w.mpl.ax.plot(lutxcoords,self.node.lut,'r')[0]
        else:
            self.plot.set_ydata(self.node.lut)
        self.w.mpl.canvas.draw() # present drawing

        # display image        
        self.w.canvas.display(self.node.img)


