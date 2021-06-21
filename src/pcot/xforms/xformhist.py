import cv2 as cv
import numpy as np

import pcot.conntypes as conntypes
import pcot.ui as ui
from pcot.channelsource import IChannelSource
from pcot.xform import xformtype, XFormType

from matplotlib import cm


def gethistogram(chan, weights, bincount):
    return np.histogram(chan, bincount, range=(0, 1), weights=weights)


@xformtype
class XFormHistogram(XFormType):
    """
    Produce a histogram of intensities for each channel in the data -
    will be very messy if used on a multispectral image."""

    def __init__(self):
        super().__init__("histogram", "data", "0.0.0")
        self.autoserialise = ('bincount',)
        self.addInputConnector("", conntypes.IMG)

    def createTab(self, n, w):
        return TabHistogram(n, w)

    def init(self, node):
        # the histogram data
        node.hists = None
        node.bincount = 256

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is not None:
            subimg = img.subimage()
            mask = ~subimg.mask
            weights = subimg.mask.astype(np.ubyte)
            # OK, brace yourself..

            # generate a list of labels, one for each channel
            labels = [IChannelSource.stringForSet(s, node.graph.doc.settings.captionType) for s in img.sources]
            # generate a (weights,bins) tuple for each channel
            hists = [gethistogram(chan, weights, node.bincount) for chan in cv.split(subimg.img)]
            # they must be the same size
            assert (len(labels) == len(hists))
            # unzips the (weights,bins) tuple list into two lists of weights and bins
            unzipped = list(zip(*hists))
            # zips the labels, weights and bins together into a list of (label,weights,bins) for each channel!
            node.hists = list(zip(labels, *unzipped))


class TabHistogram(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabhistogram.ui')
        self.w.bins.editingFinished.connect(self.binsChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.onNodeChanged()

    def replot(self):
        # set up the plot
        self.w.bins.setValue(self.node.bincount)
        if self.node.hists is not None:
            ui.log(self.node.comment)
            self.w.mpl.fig.suptitle(self.node.comment)
            self.w.mpl.ax.cla()  # clear any previous plot
            cols = cm.get_cmap('Dark2').colors
            colct = 0
            for xx in self.node.hists:
                lab, h, bins = xx
                #                bw = (bins.max()-bins.min())/self.node.bincount
                #                self.w.mpl.ax.bar(bins,h,width=bw,alpha=0.34,color=cols[colct])
                _, _, handle = self.w.mpl.ax.hist(bins[:-1], bins, weights=h, alpha=0.34, label=lab,
                                                  color=cols[colct % len(cols)])
                colct += 1
            self.w.mpl.ax.legend()
            self.w.mpl.draw()
        self.w.replot.setStyleSheet("")

    def save(self):
        self.w.mpl.save()

    def binsChanged(self):
        self.node.bincount = self.w.bins.value()
        self.changed()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")
