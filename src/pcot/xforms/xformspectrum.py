import math

import matplotlib
import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import QDialog

import pcot
import pcot.ui as ui
from pcot.datum import Datum
from pcot.filters import wav2RGB
from pcot.sources import SourceSet
from pcot.ui import uiloader
from pcot.ui.tabs import Tab
from pcot.utils.table import Table
from pcot.xform import XFormType, xformtype, XFormException


# find the mean/sd of all the masked values. Note mask negation!
def getSpectrum(chanImg, mask):
    if mask is not None:
        a = np.ma.masked_array(data=chanImg, mask=~mask)
    else:
        a = chanImg

    return a.mean(), a.std()


def processData(table, legend, data, pxct, wavelengths, spectrum, chans, chanlabels):
    """
    table: Table object for dump output
    legend: name of ROI/image
    data: data dictionary
        part of processData's responsibility is to set the entries in here
            - key is ROI/image name (legend), value is a list of data.
            - value is a list of tuples (chanidx, cwl, mean, sd, labels, pixct)
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
    means, sds, pixcts = [x[0] for x in spectrum], [x[1] for x in spectrum], [pxct for _ in spectrum]

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

COLOUR_FROMROIS = 0
COLOUR_SCHEME1 = 1
COLOUR_SCHEME2 = 2


def fixSortList(node):
    """fix the sortlist, making sure that only legends for data we have are present,
    and that all of them are present"""
    # now remove any data from the sort list which are not present in the data
    legends = node.data.keys()
    node.sortlist = [x for x in node.sortlist if x in legends]
    # and add any new items
    for x in [x for x in legends if x not in node.sortlist]:
        node.sortlist.append(x)


@xformtype
class XFormSpectrum(XFormType):
    """
    Show the mean intensities for each frequency band in each input. Each input has a separate line in
    the resulting plot, labelled with either a generated label or the annotation of the last ROI on that
    input. If two inputs have the same ROI label, they are merged into a single line."""

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('sortlist', 'errorbarmode', 'legendFontSize', 'axisFontSize', 'stackSep', 'labelFontSize',
                              'bottomSpace', 'colourmode', 'rightSpace')
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), Datum.IMG, "a single line in the plot")
        self.addOutputConnector("data", Datum.DATA, "a CSV output (use 'dump' to read it)")

    def createTab(self, n, w):
        pcot.ui.msg("creating a tab with a plot widget takes time...")
        return TabSpectrum(n, w)

    def init(self, node):
        node.errorbarmode = ERRORBARMODE_STDDEV
        node.colourmode = COLOUR_FROMROIS
        node.legendFontSize = 8
        node.axisFontSize = 8
        node.labelFontSize = 12
        node.bottomSpace = 0
        node.rightSpace = 0
        node.stackSep = 0
        node.sortlist = []  # list of legends (ROI names) - the order in which spectra should be stacked.
        node.colsByLegend = None  # this is a legend->col dictionary used if colourmode is COLOUR_FROMROIS
        node.data = None

    def perform(self, node):
        table = Table()
        # dict of output spectra, key is ROI or image name (several inputs might go into one entry if names are same, and one input might
        # have several ROIs each with a different value)
        # For each ROI/image there is a lists of tuples, one for each channel : (chanidx, wavelength, mean, sd, name)
        data = dict()
        cols = dict()  # colour dictionary for ROIs/images
        sources = set()  # sources
        for i in range(NUMINPUTS):
            img = node.getInput(i, Datum.IMG)
            if img is not None:
                # first, generate a list of indices of channels with a single source which has a wavelength,
                # and a list of those wavelengths
                wavelengths = [img.wavelength(x) for x in range(img.channels)]
                # wavelengths = [x for x in wavelengths if x > 0]     removed; given the filter on the next line it does nowt
                chans = [x for x in range(img.channels) if wavelengths[x] > 0]

                # add the channels we found to a set of sources
                for x in chans:
                    sources |= img.sources.sourceSets[x].sourceSet

                if len(wavelengths) == 0:
                    raise XFormException("DATA", "no single-wavelength channels in image")

                # generate a list of labels, one for each channel
                # NOTE THAT this currently gets ignored, we don't use the chanlabel right now. It gets packed into
                # the data elements, but the unzip in replot() throws it away when we come to do the plot.
                chanlabels = [img.sources.sourceSets[x].brief(node.graph.doc.settings.captionType) for x in chans]

                if len(img.rois) == 0:
                    # no ROIs, do the whole image
                    legend = "node input {}".format(i)
                    subimg = img.img
                    # this returns a tuple for each channel of (mean,sd)
                    spectrum = [getSpectrum(subimg[:, :, i], None) for i in chans]
                    processData(table, legend, data, img.w * img.h,
                                wavelengths, spectrum, chans, chanlabels)
                    cols[legend] = (0, 0, 0)  # what colour??

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
                    cols[legend] = roi.colour

        # now, for each list in the dict, build a new dict of the lists sorted
        # by wavelength
        node.data = {legend: sorted(lst, key=lambda x: x[1]) for legend, lst in data.items()}
        node.colsByLegend = cols  # we use this if we're using the ROI colours
        fixSortList(node)

        node.setOutput(0, Datum(Datum.DATA, table, sources=SourceSet(sources)))


class ReorderDialog(QDialog):
    def __init__(self, parent, node):
        super().__init__(parent)
        # load the UI file into the actual dialog (as the UI was created as "dialog with buttons")
        uiloader.loadUi('reorderplots.ui', self)
        self.upButton.clicked.connect(self.upClicked)
        self.downButton.clicked.connect(self.downClicked)
        self.revButton.clicked.connect(self.revClicked)
        self.listWidget.itemClicked.connect(self.itemClicked)
        self.node = node
        # add the items (we're using an item-based system rather than model-based, it's easier)
        for i in node.sortlist:
            QtWidgets.QListWidgetItem(i, self.listWidget)

        self.fixUpDown()

    def fixUpDown(self):
        if self.listWidget.currentRow() < 0:
            self.upButton.setEnabled(False)
            self.downButton.setEnabled(False)
        else:
            self.upButton.setEnabled(self.listWidget.currentRow() > 0)
            self.downButton.setEnabled(self.listWidget.currentRow() < len(self.node.sortlist) - 1)

    def itemClicked(self):
        self.fixUpDown()

    def revClicked(self):
        items = []
        while True:
            item = self.listWidget.takeItem(0)
            if item is None:
                break
            else:
                items.append(item)
        for x in items:
            self.listWidget.insertItem(0, x)

    def movecur(self, delta):
        row = self.listWidget.currentRow()
        if row >= 0:
            item = self.listWidget.takeItem(row)
            self.listWidget.insertItem(row + delta, item)
            self.listWidget.setCurrentItem(item)
            self.fixUpDown()

    def upClicked(self):
        self.movecur(-1)

    def downClicked(self):
        self.movecur(+1)

    def getNewList(self):
        return [self.listWidget.item(x).text() for x in range(self.listWidget.count())]


class TabSpectrum(ui.tabs.Tab):
    """The tab for the spectrum node"""

    def __init__(self, node, w):
        super().__init__(w, node, 'tabspectrum.ui')
        self.w.errorbarmode.currentIndexChanged.connect(self.errorbarmodeChanged)
        self.w.colourmode.currentIndexChanged.connect(self.colourmodeChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.save.clicked.connect(self.save)
        self.w.reorderButton.clicked.connect(self.openReorder)
        self.w.stackSepSpin.valueChanged.connect(self.stackSepChanged)
        self.w.legendFontSpin.valueChanged.connect(self.legendFontSizeChanged)
        self.w.axisFontSpin.valueChanged.connect(self.axisFontSizeChanged)
        self.w.labelFontSpin.valueChanged.connect(self.labelFontSizeChanged)
        self.w.bottomSpaceSpin.valueChanged.connect(self.bottomSpaceChanged)
        self.w.rightSpaceSpin.valueChanged.connect(self.rightSpaceChanged)
        self.w.hideButton.clicked.connect(self.hideClicked)
        self.nodeChanged()

    def replot(self):
        ax = self.w.mpl.ax
        # set up the plot
        self.w.mpl.fig.suptitle(self.node.comment)
        ax.cla()  # clear any previous plot

        # make sure the legend list is correct
        fixSortList(self.node)

        # pick a colour scheme for multiple plots if we're not getting the colour
        # from the ROIs
        if self.node.colourmode == COLOUR_SCHEME2:
            cols = matplotlib.cm.get_cmap('tab10').colors
        else:
            cols = matplotlib.cm.get_cmap('Dark2').colors

        # the dict consists of a list of channel data tuples for each image/roi.
        colidx = 0
        stackSep = self.node.stackSep / 20

        if stackSep != 0:  # turn off tick labels if we are stacking; the Y values would be deceptive.
            ax.set_yticklabels('')

        ax.tick_params(axis='both', labelsize=self.node.axisFontSize)
        ax.set_xlabel('wavelength', fontsize=self.node.labelFontSize)
        ax.set_ylabel('reflectance' if stackSep == 0 else 'stacked reflectance',
                      fontsize=self.node.labelFontSize)

        stackpos = 0
        for legend in self.node.sortlist:
            x = self.node.data[legend]
            try:
                [_, wavelengths, means, sds, _, pixcounts] = list(zip(*x))  # "unzip" idiom
            except ValueError:
                raise XFormException("DATA", "cannot get spectrum - problem with ROIs?")
            if self.node.colourmode == COLOUR_FROMROIS:
                col = self.node.colsByLegend[legend]
            else:
                col = cols[colidx % len(cols)]
            means = [x + stackSep * stackpos for x in means]
            ax.plot(wavelengths, means, c=col, label=legend)
            ax.scatter(wavelengths, means, c=[wav2RGB(x) for x in wavelengths], s=0)

            if self.node.errorbarmode != ERRORBARMODE_NONE:
                # calculate standard errors from standard deviations
                stderrs = [std / math.sqrt(pixels) for std, pixels in zip(sds, pixcounts)]
                ax.errorbar(wavelengths, means,
                            stderrs if self.node.errorbarmode == ERRORBARMODE_STDERROR else sds,
                            ls="None", capsize=4, c=col)
            colidx += 1
            # subtraction to make the plots stack the same way as the legend!
            stackpos -= self.node.stackSep

        ax.legend(fontsize=self.node.legendFontSize)
        ymin, ymax = ax.get_ylim()
        ax.set_ylim(ymin - self.node.bottomSpace / 10, ymax)
        xmin, xmax = ax.get_xlim()
        ax.set_xlim(xmin, xmax + self.node.rightSpace * 100)

        if self.node.stackSep == 0:  # only remove negative ticks if we're labelling the ticks.
            ax.set_yticks([x for x in ax.get_yticks() if x >= 0])

        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")

    def save(self):
        self.w.mpl.save()

    def hideClicked(self):
        self.w.controls.setVisible(not self.w.controls.isVisible())
        self.setHideButtonText()

    def setHideButtonText(self):
        self.w.hideButton.setText(
            "Hide controls" if self.w.controls.isVisible() else "Show controls"
        )

    def errorbarmodeChanged(self, mode):
        self.mark()
        self.node.errorbarmode = mode
        self.changed()

    def colourmodeChanged(self, mode):
        self.mark()
        self.node.colourmode = mode
        self.changed()

    def bottomSpaceChanged(self, val):
        self.mark()
        self.node.bottomSpace = val
        self.changed()

    def rightSpaceChanged(self, val):
        self.mark()
        self.node.rightSpace = val
        self.changed()

    def legendFontSizeChanged(self, val):
        self.mark()
        self.node.legendFontSize = val
        self.changed()

    def axisFontSizeChanged(self, val):
        self.mark()
        self.node.axisFontSize = val
        self.changed()

    def labelFontSizeChanged(self, val):
        self.mark()
        self.node.labelFontSize = val
        self.changed()

    def stackSepChanged(self, val):
        self.mark()
        self.node.stackSep = val
        self.changed()

    def openReorder(self):
        reorderDialog = ReorderDialog(self, self.node)
        if reorderDialog.exec():
            self.node.sortlist = reorderDialog.getNewList()
            self.markReplotReady()

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.markReplotReady()
        # these will each cause the widget's changed slot to get called and lots of calls to mark()
        self.w.errorbarmode.setCurrentIndex(self.node.errorbarmode)
        self.w.colourmode.setCurrentIndex(self.node.colourmode)
        self.w.stackSepSpin.setValue(self.node.stackSep)
        self.w.bottomSpaceSpin.setValue(self.node.bottomSpace)
        self.w.rightSpaceSpin.setValue(self.node.rightSpace)
        self.w.legendFontSpin.setValue(self.node.legendFontSize)
        self.w.axisFontSpin.setValue(self.node.axisFontSize)
        self.w.labelFontSpin.setValue(self.node.labelFontSize)
