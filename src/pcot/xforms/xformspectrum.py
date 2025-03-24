import dataclasses
import math

import matplotlib
import numpy as np
from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import QDialog

import pcot
import pcot.ui as ui
from pcot.datum import Datum
from pcot.cameras.filters import wav2RGB, Filter
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType
from pcot.ui import uiloader
from pcot.ui.tabs import Tab
from pcot.utils import SignalBlocker
from pcot.utils.spectrum import SpectrumSet
from pcot.value import Value
from pcot.xform import XFormType, xformtype


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
        data[legend] = []  # make a new list if there isn't one
    data[legend] += dp

    # you end up with a dict of ROI/image data e.g.
    #   "ROI/image" -> [value @ frequency, value @ frequency...]
    # where each entry in the dict should be a line in the result.


# number of inputs on the node
NUMINPUTS = 8

# short names for error bar modes used in the dialog, in the same order as they appear there
errorBarModes = ["none", "stderror", "stddev"]

# short names for colour modes used in the dialog
colourModes = ["fromROIs", "scheme1", "scheme2"]

# short names for bandwidth modes used in the dialog
bandwidthModes = ["none", "errorbar", "vertbar"]


def fixSortList(node):
    # fix the sort list, making sure that only legends for the data we have are present,
    # and that all of them are present. This list is used to "stack" items in the plot,
    # and nowhere else (it doesn't order items in the tabular output, for example).
    if node.data is not None:
        sl = node.params.sortlist.get()
        legends = node.data.keys()
        # filter out items that aren't in the data
        sl = [x for x in sl if x in legends]
        # add new items
        sl.extend([x for x in legends if x not in sl])
        node.params.sortlist.set(sl)


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
    the region. This is calculated as the variance of the means, plus the mean of the variances
    (Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012). We
    assume the number of samples that went into each pixel is the same.
    For those who might want to work with a library, SpectrumSet handles this part of the operation.

    If a point has data with BAD DQ bits in a band, those pixels are ignored in that band. If there
    are no good points, the point is not plotted for that band.

    A table of the values is also produced, and this output as a table datum. The table has one row per
    ROI or input, and the columns

    * name - the name of the ROI or input
    * m*wavelength* - the mean intensity for the given wavelength band
    * s*wavelength* - the population standard deviation of the mean intensity for the given wavelength band
    * p*wavelength* - the number of pixels in the given wavelength band (usually the same as the number of pixels in
    the ROI, but may be fewer if the ROI has "bad" pixels in that band)

    The last two columns are repeated for each wavelength band.
    """

    def __init__(self):
        super().__init__("spectrum", "data", "0.0.0")

        self.params = TaggedDictType(
            sortlist=("List of inputs to sort by", TaggedListType(str, [], '')),
            legendFontSize=("Legend font size", int, 8),
            axisFontSize=("Axis font size", int, 8),
            labelFontSize=("Label font size", int, 12),
            bottomSpace=("Bottom space", int, 0),
            rightSpace=("Right space", int, 0),
            stackSep=("Stack separation", int, 0),
            errorbarmode=("Error bar mode", str, "stddev", errorBarModes),
            colourmode=("Colour mode", str, "fromROIs", colourModes),
            bandwidthmode=("Bandwidth mode", str, "none", bandwidthModes),
            ignorePixSD=("Ignore pixel standard deviation", bool, False),
        )

        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), Datum.IMG, "a single line in the plot")
        self.addOutputConnector("data", Datum.DATA, "a CSV output (use 'dump' or 'sink' to read it)")

    def createTab(self, n, window):
        pcot.ui.msg("creating a tab with a plot widget takes time...")
        return TabSpectrum(n, window)

    def deserialise(self, n, d):
        # if certain parameters are integer, convert to index - due to LEGACY CODE.
        def conv(name, dd):
            if hasattr(n,name):
                v = getattr(n,name)
                if isinstance(v, int):
                    setattr(n, name, dd[v])
        conv('errorbarmode', errorBarModes)
        conv('colourmode', colourModes)
        conv('bandwidthmode', bandwidthModes)

    def init(self, node):
        node.data = None

    def perform(self, node):
        # first we need to create a SpectrumSet from the inputs
        inputDict = {
            f"in{i}": node.getInput(i, Datum.IMG) for i in range(NUMINPUTS)
        }
        # filter out null inputs
        inputDict = {k: v for k, v in inputDict.items() if v is not None}
        # and construct the SpectrumSet
        node.data = SpectrumSet(inputDict, ignorePixSD=node.params.ignorePixSD)
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
        for i in node.params.sortlist:
            QtWidgets.QListWidgetItem(i, self.listWidget)

        self.fixUpDown()

    def fixUpDown(self):
        if self.listWidget.currentRow() < 0:
            self.upButton.setEnabled(False)
            self.downButton.setEnabled(False)
        else:
            self.upButton.setEnabled(self.listWidget.currentRow() > 0)
            self.downButton.setEnabled(self.listWidget.currentRow() < len(self.node.params.sortlist) - 1)

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
        if self.node.params.colourmode == "scheme2":
            cols = matplotlib.cm.get_cmap('tab10').colors
        else:
            cols = matplotlib.cm.get_cmap('Dark2').colors

        # the dict consists of a list of channel data tuples for each image/roi.
        colidx = 0
        stackSep = self.node.params.stackSep / 20

        if stackSep != 0:  # turn off tick labels if we are stacking; the Y values would be deceptive.
            ax.set_yticklabels('')

        ax.tick_params(axis='both', labelsize=self.node.params.axisFontSize)
        ax.set_xlabel('wavelength', fontsize=self.node.params.labelFontSize)
        ax.set_ylabel('reflectance' if stackSep == 0 else 'stacked reflectance',
                      fontsize=self.node.params.labelFontSize)

        stackpos = 0
        for legend in self.node.params.sortlist:
            unfiltered = self.node.data[legend]

            # filter out any "masked" means - those are from regions which are entirely DQ BAD in a channel.
            # These also seem to show up as None sometimes, so we have to check for that too.

            x = {filt: spec for filt, spec in unfiltered.data.items() if spec.v is not None and
                 spec.v.n is not np.ma.masked}

            if len(x) == 0:
                ui.error(f"No points have good data for point {legend}", False)
                continue
            if len(x) != len(unfiltered.data):
                ui.error(f"Some points have bad data for point {legend}", False)

            # get a list of the filters (the dict keys) sorted by filter cwl
            filters = sorted(x.keys(), key=lambda ff: ff.cwl)

            # extract data from the dictionary
            values = [x[filt] for filt in filters]
            means = [a.v.n for a in values]
            sds = [a.v.u for a in values]
            pixcounts = [a.pixels for a in values]

            if self.node.params.colourmode == 'fromROIs':
                col = self.node.data.getColour(legend)
            else:
                col = cols[colidx % len(cols)]
            means = [x + stackSep * stackpos for x in means]

            wavelengths = [x.cwl for x in filters]

            ax.plot(wavelengths, means, c=col, label=legend)
            ax.scatter(wavelengths, means, c=[wav2RGB(x) for x in wavelengths], s=0)

            if self.node.params.errorbarmode != 'none':
                # calculate standard errors from standard deviations
                stderrs = [std / math.sqrt(pixels) for std, pixels in zip(sds, pixcounts)]
                ax.errorbar(wavelengths, means,
                            stderrs if self.node.params.errorbarmode == 'stderror' else sds,
                            # only show the x error bar if we are in the correct bandwidth mode
                            xerr=[x.fwhm / 2 for x in filters] if self.node.params.bandwidthmode == 'errorbar' else None,
                            ls="None", capsize=4, c=col)
            colidx += 1
            # subtraction to make the plots stack the same way as the legend!
            stackpos -= self.node.params.stackSep

            # now show the bandwidth as a vertical span if we are in the correct mode
            if self.node.params.bandwidthmode == 'vertbar':
                for f in filters:
                    ax.axvspan(f.cwl - f.fwhm / 2, f.cwl + f.fwhm / 2, color=col, alpha=0.1)

        ax.legend(fontsize=self.node.params.legendFontSize)
        ymin, ymax = ax.get_ylim()
        ymin = ymin - self.node.params.bottomSpace / 10
        if ymax - ymin < 0.01:  # if the y range is too small, expand it
            ymin -= 0.01
            ymax += 0.01
        ax.set_ylim(ymin, ymax)
        xmin, xmax = ax.get_xlim()
        ax.set_xlim(xmin, xmax + self.node.params.rightSpace * 100)

        if self.node.params.stackSep == 0:  # only remove negative ticks if we're labelling the ticks.
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
        self.node.params.ignorePixSD = state == QtCore.Qt.Checked
        self.changed()

    def errorbarmodeChanged(self, mode):
        self.mark()
        self.node.params.errorbarmode = errorBarModes[mode]
        self.changed()

    def bandwidthmodeChanged(self, mode):
        self.mark()
        self.node.params.bandwidthmode = bandwidthModes[mode]
        self.changed()

    def colourmodeChanged(self, mode):
        self.mark()
        self.node.params.colourmode = colourModes[mode]
        self.changed()

    def bottomSpaceChanged(self, val):
        self.mark()
        self.node.params.bottomSpace = val
        self.changed()

    def rightSpaceChanged(self, val):
        self.mark()
        self.node.params.rightSpace = val
        self.changed()

    def legendFontSizeChanged(self, val):
        self.mark()
        self.node.params.legendFontSize = val
        self.changed()

    def axisFontSizeChanged(self, val):
        self.mark()
        self.node.params.axisFontSize = val
        self.changed()

    def labelFontSizeChanged(self, val):
        self.mark()
        self.node.params.labelFontSize = val
        self.changed()

    def stackSepChanged(self, val):
        self.mark()
        self.node.params.stackSep = val
        self.changed()

    def openReorder(self):
        reorderDialog = ReorderDialog(self, self.node)
        if reorderDialog.exec():
            self.node.params.sortlist.set(reorderDialog.getNewList())
            self.markReplotReady()

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def onNodeChanged(self):
        # this is done in replot - the user replots this node manually because it takes
        # a while to run. But we do make the replot button red!
        self.markReplotReady()
        # these could each cause the widget's changed slot to get called and lots of calls to mark();
        # hopefully the signal blocking will prevent that.
        with SignalBlocker(self.w.errorbarmode, self.w.bandwidthmode, self.w.colourmode,
                           self.w.stackSepSpin, self.w.bottomSpaceSpin, self.w.rightSpaceSpin,
                           self.w.legendFontSpin, self.w.axisFontSpin, self.w.labelFontSpin,
                           self.w.ignorePixSD):
            self.w.errorbarmode.setCurrentIndex(errorBarModes.index(self.node.params.errorbarmode))
            self.w.bandwidthmode.setCurrentIndex(bandwidthModes.index(self.node.params.bandwidthmode))
            self.w.colourmode.setCurrentIndex(colourModes.index(self.node.params.colourmode))
            self.w.stackSepSpin.setValue(self.node.params.stackSep)
            self.w.bottomSpaceSpin.setValue(self.node.params.bottomSpace)
            self.w.rightSpaceSpin.setValue(self.node.params.rightSpace)
            self.w.legendFontSpin.setValue(self.node.params.legendFontSize)
            self.w.axisFontSpin.setValue(self.node.params.axisFontSize)
            self.w.labelFontSpin.setValue(self.node.params.labelFontSize)
            self.w.ignorePixSD.setChecked(self.node.params.ignorePixSD)
