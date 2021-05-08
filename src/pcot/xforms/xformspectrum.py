from functools import partial

import numpy as np
import csv, io
from matplotlib import cm

import pcot.conntypes as conntypes
import pcot.ui as ui
from pcot.channelsource import IChannelSource
from pcot.filters import wav2RGB
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


# utility class which might get moved elsewhere. Provides a structure
# consisting of a list of keys, and a list of dicts. Each dict contains values for the keys,
# although None is a permissible value (and the default). Start a new row with newRow.
# Then add k/v pairs. Access via __getitem__ on this object (I think); because direct dict access
# would be bad. So it's a bit like csv.DictWriter, but deals with ignored data.

class TableIter:
    def __init__(self, table):
        self.table = table
        self.iter = table._rows.__iter__()

    def __iter__(self):
        return self

    def __next__(self):
        row = self.iter.__next__()
        return [row[k] if k in row else 'NA' for k in self.table.keys()]


class Table:
    def __init__(self):
        self._keys = []
        self._rows = []
        self._currow = None

    def newRow(self):
        self._currow = dict()
        self._rows.append(self._currow)

    def add(self, k, v):
        if k not in self._keys:
            self._keys.append(k)
        self._currow[k] = v

    def keys(self):
        return self._keys

    def __iter__(self):
        return TableIter(self)

    def __str__(self):
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(self._keys)
        for r in self:
            w.writerow(r)
        return s.getvalue()


NUMINPUTS = 5


@xformtype
class XFormSpectrum(XFormType):
    """Produce a histogram for each channel in the data"""

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('mode',)
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), "img")
        self.addOutputConnector("data", conntypes.DATA)

    def createTab(self, n, w):
        return TabSpectrum(n, w)

    def init(self, node):
        node.mode = 0
        node.data = None

    def perform(self, node):
        table = Table()
        data = []  # list of output spectra, one for each active input
        for i in range(NUMINPUTS):
            img = node.getInput(i, conntypes.IMG)
            if img is not None:
                legend = img.getROIName()  # this is a name attached to one of the image's ROIs
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

                # zip them all together and sort by wavelength
                data.append((legend, sorted(zip(chans, wavelengths, spectrum, labels), key=lambda x: x[1])))

                # add to table
                table.newRow()
                table.add("name", legend)
                table.add("pixels", subimg.pixelCount())
                for w, s in zip(wavelengths, spectrum):
                    table.add(w, s)
                node.setOutput(0, Datum(conntypes.DATA, table))

        table.add("wibble", 0)
        node.data = data


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

        for legend, x in self.node.data:
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
