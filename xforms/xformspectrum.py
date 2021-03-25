from functools import partial

import numpy as np
from matplotlib import cm

import conntypes
import ui
from channelsource import IChannelSource
from filters import wav2RGB
from xform import XFormType, xformtype


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


@xformtype
class XFormSpectrum(XFormType):
    """Produce a histogram for each channel in the data"""

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('mode',)
        self.addInputConnector("", "img")

    def createTab(self, n, w):
        return TabSpectrum(n, w)

    def init(self, node):
        node.mode = 0
        node.data = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is not None:
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
            node.data = sorted(zip(chans, wavelengths, spectrum, labels), key=lambda x: x[1])
        else:
            node.data = None


class TabSpectrum(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabspectrum.ui')
        self.w.mode.currentIndexChanged.connect(self.modeChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.onNodeChanged()

    def replot(self):
        # set up the plot
        if self.node.data is not None:
            self.w.mpl.fig.suptitle(self.node.comment)
            self.w.mpl.ax.cla()  # clear any previous plot
            cols = cm.get_cmap('Dark2').colors

            [chans, wavelengths, spectrum, labels] = list(zip(*self.node.data))  # "unzip" idiom
            self.w.mpl.ax.plot(wavelengths, spectrum)
            self.w.mpl.ax.scatter(wavelengths,spectrum,c=[wav2RGB(x) for x in wavelengths])
            for _, wv, sp, lab in self.node.data:
                self.w.mpl.ax.annotate(lab, (wv, sp), textcoords='offset points', xytext=(0, 10), ha='center')

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
