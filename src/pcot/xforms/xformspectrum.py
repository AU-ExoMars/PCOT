import math
import pprint

import numpy as np
from matplotlib import cm

import pcot.conntypes as conntypes
import pcot.ui as ui
from pcot.channelsource import IChannelSource
from pcot.filters import wav2RGB
from pcot.utils.table import Table
from pcot.xform import XFormType, xformtype, XFormException


# find the mean/sd of all the masked values. Note mask negation!
def getSpectrum(chanImg, mask):
    if mask is not None:
        a = np.ma.masked_array(data=chanImg, mask=~mask)
    else:
        a = chanImg

    return a.mean(), a.std()


# return wavelength if channel is a single source from a filtered input, else -1.
def wavelength(channelNumber, img):
    source = img.sources[channelNumber]
    if len(source) != 1:
        return -1
    # looks weird, but just unpacks this single-item set
    [source] = source
    return source.getFilter().cwl


def processData(table, legend, data, pxct, wavelengths, spectrum, chans, chanlabels):
    """
    table: Table object for dump output
    legend: name of ROI/image
    data: data dictionary
        part of processData's responsibility is to set the entries in here
            - key is ROI/image name, value is a list of data.
            - valiue is a list of tuples (chanidx, cwl, mean, sd, labels, pixct)
    Then a list for each channel, giving
        wavelengths:    cwl of channel
        spectrum        (mean,sd) of intensity across ROI/image for this channel

    Consider two images. Image 0 has an ROI with 3132 pixels in it, image 1 has an ROI
    with only 484 pixels in it. However, the two ROIs both have the same name, and are fed
    into a spectrum. They will be combined into a single data list looking like this:
    [
        # channel index, cwl, mean intensity, sd of intensity, channel label, pixel count
       (0, 438.0, 0.09718827482688777, 0.033184560153696856, 'L4_438', 3132),
        (1, 500.0, 0.12427511008154235, 0.04296475099012811, 'L5_500', 3132),
        (2, 532.0, 0.15049515647449713, 0.04899176061731549, 'L6_532', 3132),
        (3, 568.0, 0.18620748507717713, 0.05834286572257662, 'L7_568', 3132),
        (4, 610.0, 0.23161822595511056, 0.07227542372780232, 'L8_610', 3132),
        (5, 671.0, 0.2626209478268678, 0.08226790002558386, 'L9_671', 3132),
        (0, 740.0, 0.3917202910115896, 0.08213716515845079, 'R4_740', 484),
        (1, 780.0, 0.41594551023372933, 0.08695280835403581, 'R5_780', 484),
        (2, 832.0, 0.39478648792613635, 0.08164454531723438, 'R6_832', 484),
        (3, 900.0, 0.37751833072378616, 0.07634822775362438, 'R7_900', 484),
        (4, 950.0, 0.3726376304941729, 0.07310612483354316, 'R8_950', 484),
        (5, 1000.0, 0.4105814784026343, 0.08091608212909969, 'R9_1000', 484)]
    ]

    This should mean that the standard error will be calculated correctly for both of the ROI.
    """

    # zip them all together and append to the list for that legend (creating a new list
    # if there isn't one)
    if legend not in data:
        data[legend] = []

    # spectrum is [(mean,sd), (mean,sd)...] but we also build a pixcount array
    means, sds, pixcts = [x[0] for x in spectrum], [x[1] for x in spectrum], [pxct for x in spectrum]

    # data for each region is [ (chan,wave,mean,sd,chanlabel,pixcount), (chan,wave,mean,sd,chanlabel,pixcount)..]
    # This means pixcount get dupped a lot but it's not a problem
    data[legend] += list(zip(chans, wavelengths, means, sds, chanlabels, pixcts))

    # add to table
    table.newRow(legend)
    table.add("name", legend)
    table.add("pixels", pxct)
    for w, s in zip(wavelengths, spectrum):
        m, sd = s
        w = int(w)  # Convert wavelength to integer for better table form. Let's hope this doesn't cause problems.
        table.add("{}mean".format(w), m)
        table.add("{}sd".format(w), sd)


NUMINPUTS = 8


ERRORBARMODE_NONE = 0
ERRORBARMODE_STDERROR = 1
ERRORBARMODE_STDDEV = 2


@xformtype
class XFormSpectrum(XFormType):
    """Show the mean intensities for each frequency band in each input. Each input has a separate line in
    the resulting plot, labelled with either a generated label or the annotation of the last ROI on that
    input. If two inputs have the same ROI label, they are merged into a single line."""

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('errorbarmode',)
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), conntypes.IMG, "a single line in the plot")
        self.addOutputConnector("data", conntypes.DATA, "a CSV output (use 'dump' to read it)")

    def createTab(self, n, w):
        return TabSpectrum(n, w)

    def init(self, node):
        node.errorbarmode = 0
        node.data = None

    def perform(self, node):
        table = Table()
        # dict of output spectra, key is ROI or image name (several inputs might go into one entry if names are same, and one input might
        # have several ROIs each with a different value)
        # For each ROI/image there is a lists of tuples, one for each channel : (chanidx, wavelength, mean, sd, name)
        data = dict()
        for i in range(NUMINPUTS):
            img = node.getInput(i, conntypes.IMG)
            if img is not None:
                # first, generate a list of indices of channels with a single source which has a wavelength,
                # and a list of those wavelengths
                wavelengths = [wavelength(x, img) for x in range(img.channels)]
                chans = [x for x in range(img.channels) if wavelengths[x] > 0]
                wavelengths = [x for x in wavelengths if x > 0]

                # generate a list of labels, one for each channel
                chanlabels = [IChannelSource.stringForSet(img.sources[x],
                                                          node.graph.doc.settings.captionType) for x in chans]

                if len(img.rois) == 0:
                    # no ROIs, do the whole image
                    legend = "node input {}".format(i)
                    subimg = img.img
                    # this returns a tuple for each channel of (mean,sd)
                    spectrum = [getSpectrum(subimg[:, :, i], None) for i in chans]
                    processData(table, legend, data, img.w * img.h,
                                wavelengths, spectrum, chans, chanlabels)

                for roi in img.rois:
                    # only include valid ROIs
                    if roi.bb() is None:
                        continue
                    legend = roi.label  # get the name for this ROI, which will appear as a thingy.
                    # get the ROI bounded image
                    subimg = img.subimage(roi=roi)
                    # now we need to get the mean amplitude of the pixels in each channel in the ROI
                    # this returns a tuple for each channel of (mean,sd)
                    spectrum = [getSpectrum(subimg.img[:, :, i], subimg.mask) for i in chans]
                    processData(table, legend, data, subimg.pixelCount(),
                                wavelengths, spectrum, chans, chanlabels)

        # now, for each list in the dict, build a new dict of the lists sorted
        # by wavelength
        node.data = {legend: sorted(lst, key=lambda x: x[1]) for legend, lst in data.items()}

        node.setOutput(0, conntypes.Datum(conntypes.DATA, table))


class TabSpectrum(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabspectrum.ui')
        self.w.errorbarmode.currentIndexChanged.connect(self.errorbarmodeChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.onNodeChanged()

    def replot(self):
        # set up the plot
        self.w.mpl.fig.suptitle(self.node.comment)
        self.w.mpl.ax.cla()  # clear any previous plot
        cols = cm.get_cmap('Dark2').colors

        # the dict consists of a list of channel data tuples for each image/roi.
        colidx = 0
        for legend, x in self.node.data.items():
            try:
                [chans, wavelengths, means, sds, labels, pixcounts] = list(zip(*x))  # "unzip" idiom
            except ValueError:
                raise XFormException("cannot get spectrum - problem with ROIs?")
            col = cols[colidx%len(cols)]
            self.w.mpl.ax.plot(wavelengths, means, label=legend, c=col)
            self.w.mpl.ax.scatter(wavelengths, means, c=[wav2RGB(x) for x in wavelengths])

            if self.node.errorbarmode != ERRORBARMODE_NONE:
                # calculate standard errors from standard deviations
                stderrs = [std / math.sqrt(pixels) for std, pixels in zip(sds, pixcounts)]
                self.w.mpl.ax.errorbar(wavelengths, means,
                                       stderrs if self.node.errorbarmode == ERRORBARMODE_STDERROR else sds,
                                       ls="None", capsize=4, c=col)
            colidx += 1
        #            for _, wv, sp, lab in x:
        #                self.w.mpl.ax.annotate(lab, (wv, sp), textcoords='offset points', xytext=(0, 10), ha='center')
        self.w.mpl.ax.legend()
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")

    def save(self):
        self.w.mpl.save()

    def errorbarmodeChanged(self, mode):
        self.node.errorbarmode = mode
        self.changed()

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")
        self.w.errorbarmode.setCurrentIndex(self.node.errorbarmode)
