import dataclasses
import math

import matplotlib
import numpy as np
from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import QDialog

import pcot
import pcot.ui as ui
from pcot.datum import Datum
from pcot.filters import wav2RGB, Filter
from pcot.sources import SourceSet
from pcot.ui import uiloader
from pcot.ui.tabs import Tab
from pcot.utils.spectrum import Spectrum, SpectrumSet
from pcot.utils.table import Table
from pcot.value import Value
from pcot.xform import XFormType, xformtype, XFormException


def processData(legend, data, spec):
    """
    Process the data from a single ROI/image into the data dictionary, which contains

    legend: name of ROI/image to be added.
    data: data dictionary
        processData's responsibility is to add to the entries in here
            - key is ROI/image name (legend), value is a list of data.
            - value is a list of tuples - see below - (chanidx, filter, mean, sd, label, pixct)
    spec: a Spectrum object describing the spectrum for this ROI/image
    """

    @dataclasses.dataclass
    class DataPoint:
        # this is our data point object.
        chan: int
        filter: Filter
        value: Value
        pixcount: int

    # build the data points
    dp = []
    for i in range(spec.channels):
        p = spec.getByChannel(i)
        if p is not None:
            p = DataPoint(i, spec.filters[i], p.v, p.pixels)
            dp.append(p)

    # now we have a list of data points - channel, filter, value, pixcount.

    # add them to the data set, which is indexed by legend (ROI or image name).
    if legend not in data:
        data[legend] = []   # make a new list if there isn't one
    data[legend] += dp

    # you end up with a dict of ROI/image data e.g.
    #   "ROI/image" -> [value @ frequency, value @ frequency...]
    # where each entry in the dict should be a line in the result.


# number of inputs on the node
NUMINPUTS = 8

# enums for error bar modes used in the dialog
ERRORBARMODE_NONE = 0
ERRORBARMODE_STDERROR = 1
ERRORBARMODE_STDDEV = 2

# enums for colour modes used in the dialog
COLOUR_FROMROIS = 0
COLOUR_SCHEME1 = 1
COLOUR_SCHEME2 = 2

# enums for bandwidth modes used in the dialog
BANDWIDTHMODE_NONE = 0
BANDWIDTHMODE_ERRORBAR = 1
BANDWIDTHMODE_VERTBAR = 2


def fixSortList(node):
    # fix the sort list, making sure that only legends for the data we have are present,
    # and that all of them are present. This list is used to "stack" items in the plot,
    # and nowhere else (it doesn't order items in the tabular output, for example).
    legends = node.data.keys()
    # filter out items that aren't in the data
    node.sortlist = [x for x in node.sortlist if x in legends]
    # add new items
    node.sortlist.extend([x for x in legends if x not in node.sortlist])


@xformtype
class XFormSpectrum(XFormType):
    """
    Show the mean intensities for each frequency band in each region of interest (ROI) in each input.
    If an input has no ROI, the intensities of all the pixels in the input are used.

    It's quite possible for the different inputs to be different images, to permit comparison.

    Each region (or input) has a separate line in
    the resulting plot, labelled with the annotation for the ROI (or "inputN" for an input with no ROI).
    If ROIs in different inputs have the same annotation, they are labelled as "inN:annotation" where N is
    the input number.

    Each pixel has its own variance, so the shown variance is the pooled variance of all the pixels in
    the region. This is calculated as the variance of the means, plus the mean of the variances.

    If a point has data with BAD DQ bits in a band, those pixels are ignored in that band. If there
    are no good points, the point is not plotted for that band.

    A table of the values is also produced, and this output as CSV text. The table has one row per
    ROI or input, and the columns

    * name - the name of the ROI or input
    * m*wavelength* - the mean intensity for the given wavelength band
    * s*wavelength* - the standard deviation of the mean intensity for the given wavelength band
    * p*wavelength* - the number of pixels in the given wavelength band (usually the same as the number of pixels in
    the ROI, but may be fewer if the ROI has "bad" pixels in that band)

    The last two columns are repeated for each wavelength band.
    """

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('sortlist', 'errorbarmode', 'legendFontSize', 'axisFontSize', 'stackSep', 'labelFontSize',
                              'bottomSpace', 'colourmode', 'rightSpace',
                              # these have defaults because they were developed later.
                              ('ignorePixSD', False),
                              ('bandwidthmode', BANDWIDTHMODE_NONE),
                              )
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), Datum.IMG, "a single line in the plot")
        self.addOutputConnector("data", Datum.DATA, "a CSV output (use 'dump' or 'sink' to read it)")

    def createTab(self, n, window):
        pcot.ui.msg("creating a tab with a plot widget takes time...")
        return TabSpectrum(n, window)

    def init(self, node):
        node.errorbarmode = ERRORBARMODE_STDDEV
        node.colourmode = COLOUR_FROMROIS
        node.bandwidthmode = BANDWIDTHMODE_NONE
        node.legendFontSize = 8
        node.axisFontSize = 8
        node.labelFontSize = 12
        node.bottomSpace = 0
        node.rightSpace = 0
        node.stackSep = 0
        node.ignorePixSD = self.getAutoserialiseDefault('ignorePixSD')
        node.sortlist = []  # list of legends (ROI names) - the order in which spectra should be stacked.
        node.data = None

    def perform(self, node):
        # first we need to create a SpectrumSet from the inputs
        inputDict = {
            f"in{i}": node.getInput(i, Datum.IMG) for i in range(NUMINPUTS)
        }
        # filter out null inputs
        inputDict = {k: v for k, v in inputDict.items() if v is not None}
        # and construct the SpectrumSet
        node.data = SpectrumSet(inputDict, ignorePixSD=node.ignorePixSD)
        fixSortList(node)
        node.setOutput(0, Datum(Datum.DATA, node.data.table(), sources=node.data.getSources()))


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
        self.w.bandwidthmode.currentIndexChanged.connect(self.bandwidthmodeChanged)
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
        self.w.ignorePixSD.stateChanged.connect(self.ignorePixSDChanged)
        self.nodeChanged()

    def replot(self):
        ax = self.w.mpl.ax
        # set up the plot
        # self.w.mpl.fig.suptitle("TODO")  # TODO? Do we need a title?
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
            unfiltered = self.node.data[legend]

            # filter out any "masked" means - those are from regions which are entirely DQ BAD in a channel.
            # These also seem to show up as None sometimes, so we have to check for that too.

            x = {filt: spec for filt, spec in unfiltered.data.items() if spec.v is not None and spec.v.n is not np.ma.masked}

            if len(x) == 0:
                ui.error(f"No points have good data for point {legend}", False)
                continue
            if len(x) != len(unfiltered.data):
                ui.error(f"Some points have bad data for point {legend}", False)

            # extract data from the dictionary
            filters = x.keys()
            values = x.values()
            means = [a.v.n for a in values]
            sds = [a.v.u for a in values]
            pixcounts = [a.pixels for a in values]

            if self.node.colourmode == COLOUR_FROMROIS:
                col = self.node.data.getColour(legend)
            else:
                col = cols[colidx % len(cols)]
            means = [x + stackSep * stackpos for x in means]

            wavelengths = [x.cwl for x in filters]

            ax.plot(wavelengths, means, c=col, label=legend)
            ax.scatter(wavelengths, means, c=[wav2RGB(x) for x in wavelengths], s=0)

            if self.node.errorbarmode != ERRORBARMODE_NONE:
                # calculate standard errors from standard deviations
                stderrs = [std / math.sqrt(pixels) for std, pixels in zip(sds, pixcounts)]
                ax.errorbar(wavelengths, means,
                            stderrs if self.node.errorbarmode == ERRORBARMODE_STDERROR else sds,
                            # only show the x error bar if we are in the correct bandwidth mode
                            xerr=[x.fwhm / 2 for x in filters] if self.node.bandwidthmode == BANDWIDTHMODE_ERRORBAR else None,
                            ls="None", capsize=4, c=col)
            colidx += 1
            # subtraction to make the plots stack the same way as the legend!
            stackpos -= self.node.stackSep

            # now show the bandwidth as a vertical span if we are in the correct mode
            if self.node.bandwidthmode == BANDWIDTHMODE_VERTBAR:
                for f in filters:
                    ax.axvspan(f.cwl - f.fwhm / 2, f.cwl + f.fwhm / 2, color=col, alpha=0.1)

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

    def ignorePixSDChanged(self, state):
        self.mark()
        self.node.ignorePixSD = state == QtCore.Qt.Checked
        self.changed()

    def errorbarmodeChanged(self, mode):
        self.mark()
        self.node.errorbarmode = mode
        self.changed()

    def bandwidthmodeChanged(self, mode):
        self.mark()
        self.node.bandwidthmode = mode
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
        self.w.bandwidthmode.setCurrentIndex(self.node.bandwidthmode)
        self.w.colourmode.setCurrentIndex(self.node.colourmode)
        self.w.stackSepSpin.setValue(self.node.stackSep)
        self.w.bottomSpaceSpin.setValue(self.node.bottomSpace)
        self.w.rightSpaceSpin.setValue(self.node.rightSpace)
        self.w.legendFontSpin.setValue(self.node.legendFontSize)
        self.w.axisFontSpin.setValue(self.node.axisFontSize)
        self.w.labelFontSpin.setValue(self.node.labelFontSize)
