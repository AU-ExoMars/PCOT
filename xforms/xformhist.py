from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.mplwidget
from xform import xformtype,XFormType
from pancamimage import Image

def gethistogram(chan,weights,bincount):
    return np.histogram(chan,bincount,weights=weights)


@xformtype
class XFormHistogram(XFormType):
    """Produce a histogram for each channel in the data"""
    def __init__(self):
        super().__init__("histogram","0.0.0")
        self.addInputConnector("","img")

    def createTab(self,n):
        return TabHistogram(n)        
        
    def init(self,node):
        # the histogram data
        node.hists = None
        node.bincount = 256
        
    def perform(self,node):
        print("PERFORM")
        img = node.getInput(0)
        if img is not None:
            subimg = img.subimage()
            mask = ~subimg.mask
            weights = subimg.mask.astype(np.ubyte)
            node.hists = [ gethistogram(chan,weights,node.bincount) for chan in cv.split(subimg.img)]

class TabHistogram(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabhistogram.ui')
        self.w.bins.editingFinished.connect(self.binsChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.onNodeChanged()
        
    def replot(self):
        # set up the plot
        print(self.node.bincount)
        self.w.bins.setValue(self.node.bincount)
        if self.node.hists is not None:
            ui.mainui.log(self.node.comment)
            self.w.mpl.fig.suptitle(self.node.comment)
            self.w.mpl.ax.cla() # clear any previous plot
            cols=[ 'r','g','b']
            colct=0
            for xx in self.node.hists:
                h,bins = xx
                bins=bins[:-1]
                self.w.mpl.ax.bar(bins,h,alpha=0.34,color=cols[colct])
                colct+=1
            self.w.mpl.draw()
        self.w.replot.setStyleSheet("")

    def save(self):
        self.w.mpl.save()
        
    def binsChanged(self):
        self.node.bincount=self.w.bins.value()
        self.node.perform()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")
