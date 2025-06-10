import numpy as np

from pcot import ui
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.sources import SourceSet
from pcot.ui.tabs import Tab
from pcot.utils import image
from pcot.utils.table import Table
from pcot.xform import xformtype, XFormType

from matplotlib import cm


def gethistogram(chan, weights, bincount, range):
    r = np.histogram(chan, bincount, range=range, weights=weights)
    return r  # split out for debugging


@xformtype
class XFormHistogram(XFormType):
    """
    Produce a histogram of intensities for each channel in the data -
    will be very messy if used on a multispectral image.

    Will only be performed on ROIs if there are active ROIs. BAD pixels
    in bands will be discounted.

    The output carries a table - columns are frequencies, rows are bands.

    **Uncertainty is ignored.**
    """

    def __init__(self):
        super().__init__("histogram", "data", "0.0.0")
        self.params = TaggedDictType(
            bincount = ("Number of bins in the histogram", int, 16)
        )
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("data", Datum.DATA, "a CSV output (use 'dump' or 'sink' to read it)")

    def createTab(self, n, w):
        ui.msg("creating a tab with a plot widget takes time...")
        return TabHistogram(n, w)

    def init(self, node):
        # the histogram data
        node.hists = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            subimg = img.subimage()
            # we get a mask - this has a layer for each channel. Each True value will be considered a weight of 1,
            # each False is a weight of 0. That means that areas outside the ROI and BAD pixels in channels will
            # not be counted.
            weights = subimg.fullmask(True).astype(float)  # ignore BAD pixels and convert to 0 or 1
            # generate a list of labels, one for each channel
            labels = [s.brief(node.graph.doc.settings.captionType) for s in img.sources.sourceSets]
            # generate a (data,bins) tuple for each channel taking account of the weight for that channel.
            range = (subimg.img.min(), subimg.img.max())
            if subimg.img.ndim == 2:
                # single band image
                hists = [gethistogram(subimg.img, weights[:, :], node.params.bincount, range=range)]
            else:
                hists = [gethistogram(chan, weights[:, :, i], node.params.bincount, range=range) for i, chan in
                         enumerate(image.imgsplit(subimg.img))]
            # they must be the same size
            assert (len(labels) == len(hists))
            # unzips the (data,bins) tuple list into two lists of data and bins
            unzipped = list(zip(*hists))
            # zips the labels, data and bins together into a list of (label,data,bins) for each channel!
            node.hists = list(zip(labels, *unzipped))

            # generate a table for output
            t = Table()
            for lab, dat, bins in node.hists:
                t.newRow(lab)
                t.add('band', lab)
                for k, v in zip(bins, dat):
                    t.add(k, v)

            node.setOutput(0, Datum(Datum.DATA, t, sources=SourceSet(img.sources.getSources())))
        else:
            node.setOutput(0, None)


class TabHistogram(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabhistogram.ui')
        self.w.bins.editingFinished.connect(self.binsChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.nodeChanged()

    def replot(self):
        # set up the plot
        self.w.bins.setValue(self.node.params.bincount)
        if self.node.hists is not None:
            # self.w.mpl.fig.suptitle("TODO")  # TODO? Do we need a title?
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
        self.mark()
        self.node.params.bincount = self.w.bins.value()
        self.changed()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")
        self.w.bins.setValue(self.node.params.bincount)
