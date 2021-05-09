import numpy as np
from matplotlib import cm

import pcot.conntypes as conntypes
import pcot.ui as ui
from pcot.channelsource import IChannelSource
from pcot.filters import wav2RGB
from pcot.utils.table import Table
from pcot.xform import XFormType, xformtype, Datum


# find the mean of all the masked values. Note mask negation!
def getSpectrum(chanImg, mask):
    return np.ma.masked_array(data=chanImg, mask=~mask).mean()


# return  wavelength if channel is a single source from a filtered input, else -1.
def wavelength(channelNumber, img):
    source = img.sources[channelNumber]
    if len(source) != 1:
        return -1
    # looks weird, but just unpacks this single-item set
    [source] = source
    return source.getFilter().cwl


NUMINPUTS = 8


@xformtype
class XFormSpectrum(XFormType):
    """Show the mean intensities for each frequency in each input. Each input has a separate line in
    the resulting plot, labelled with either a generated label or the annotation of the last ROI on that
    input. If two inputs have the same ROI label, they are merged into a single line."""

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('mode',)
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), conntypes.IMG, "a single line in the plot")
        self.addOutputConnector("data", conntypes.DATA, "a CSV output (use 'dump' to read it)")

    def createTab(self, n, w):
        return TabSpectrum(n, w)

    def init(self, node):
        node.mode = 0
        node.data = None

    def perform(self, node):
        table = Table()
        data = dict()  # dict of output spectra, key is input name (several inputs might go into one entry if names are same)
        for i in range(NUMINPUTS):
            img = node.getInput(i, conntypes.IMG)
            if img is not None:
                legend = img.getROIName()  # this is an annotation attached to one of the image's ROIs
                if legend is None:      # and if there isn't an annotation, use "input n"
                    legend = "input {}".format(i)

                # first, generate a list of indices of channels with a single source which has a wavelength,
                # and a list of those wavelengths
                wavelengths = [wavelength(x, img) for x in range(img.channels)]
                chans = [x for x in range(img.channels) if wavelengths[x] > 0]
                wavelengths = [x for x in wavelengths if x > 0]

                # generate a list of labels, one for each channel
                labels = [IChannelSource.stringForSet(img.sources[x], node.graph.captionType) for x in chans]

                # get the ROI bounded image
                subimg = img.subimage()
                # now we need to get the mean amplitude of the pixels in each channel in the ROI
                spectrum = [getSpectrum(subimg.img[:, :, i], subimg.mask) for i in chans]

                # zip them all together and append to the list for that legend (creating a new list
                # if there isn't one)
                if legend not in data:
                    data[legend] = []
                data[legend] += list(zip(chans, wavelengths, spectrum, labels))

                # add to table
                table.newRow(legend)
                table.add("name", legend)
                table.add("pixels", subimg.pixelCount())
                for w, s in zip(wavelengths, spectrum):
                    table.add(w, s)
                node.setOutput(0, Datum(conntypes.DATA, table))

        # now, for each list in the dict, build a new dict of the lists sorted
        # by wavelength

        node.data = {legend: sorted(lst, key=lambda x: x[1]) for legend, lst in data.items()}


class TabSpectrum(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabspectrum.ui')
        self.w.mode.currentIndexChanged.connect(self.modeChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.onNodeChanged()

    def replot(self):
        # set up the plot
        self.w.mpl.fig.suptitle(self.node.comment)
        self.w.mpl.ax.cla()  # clear any previous plot
        cols = cm.get_cmap('Dark2').colors

        for legend, x in self.node.data.items():
            [chans, wavelengths, spectrum, labels] = list(zip(*x))  # "unzip" idiom
            self.w.mpl.ax.plot(wavelengths, spectrum, label=legend)
            self.w.mpl.ax.scatter(wavelengths, spectrum, c=[wav2RGB(x) for x in wavelengths])
        #            for _, wv, sp, lab in x:
        #                self.w.mpl.ax.annotate(lab, (wv, sp), textcoords='offset points', xytext=(0, 10), ha='center')
        self.w.mpl.ax.legend()
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")

    def save(self):
        self.w.mpl.save()

    def modeChanged(self, mode):
        self.node.mode = mode
        self.changed()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")
