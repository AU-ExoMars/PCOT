from pcot import ui
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.plotting.histogramplot import plotHistogram
from pcot.ui.tabs import Tab
from pcot.ui import theme
from pcot.utils.histogram import Histogram
from pcot.xform import xformtype, XFormType


@xformtype
class XFormHistogram(XFormType):
    """
    Produce a histogram of intensities for each channel in the data -
    will be very messy if used on a multispectral image.

    Will only be performed on ROIs if there are active ROIs. BAD pixels
    in bands will be discounted. All bands share the same bins, which span
    the range of the pixels counted.

    The output is histogram data, which can be viewed as a table (a row for
    each bin, a column for each band) or saved as CSV.

    **Uncertainty is ignored.**
    """

    def __init__(self):
        super().__init__("histogram", "data", "0.0.0")
        self.params = TaggedDictType(
            bincount = ("Number of bins in the histogram", int, 16)
        )
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("data", Datum.HISTOGRAM, "a histogram (use 'dump' or 'sink' to read it)")

    def createTab(self, n, w):
        ui.msg("creating a tab with a plot widget takes time...")
        return TabHistogram(n, w)

    def init(self, node):
        # the histogram data, a pcot.utils.histogram.Histogram
        node.data = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            node.data = Histogram.fromImage(img, node.params.bincount)
            node.setOutput(0, Datum(Datum.HISTOGRAM, node.data, node.data.getSources()))
        else:
            node.data = None
            node.setOutput(0, None)


class TabHistogram(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabhistogram.ui')
        self.w.bins.editingFinished.connect(self.binsChanged)
        self.w.replot.clicked.connect(self.replot)
        self.nodeChanged()

    def replot(self):
        # set up the plot
        self.w.bins.setValue(self.node.params.bincount)
        if self.node.data is not None:
            plotHistogram(self.w.mpl.ax, self.node.data)
            self.w.mpl.draw()
        theme.setStaleStyle(self.w.replot, False)

    def binsChanged(self):
        self.mark()
        self.node.params.bincount = self.w.bins.value()
        self.changed()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        theme.setStaleStyle(self.w.replot, True)
        self.w.bins.setValue(self.node.params.bincount)
