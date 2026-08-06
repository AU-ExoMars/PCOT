import builtins
import logging
import dataclasses
from typing import List, Dict, Tuple

import numpy as np
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

import pcot.ui.tabs
from pcot import cameras, ui
import pcot.calib
from pcot.assets import Icons
from pcot.calib import SimpleValue
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe
from pcot.ui.help import showHelpDialog
from pcot.ui.tabledialog import TableDialog
from pcot.ui import theme
from pcot.utils import SignalBlocker, image
from pcot.utils.maths import pooled_sd
from pcot.utils.table import Table
from pcot.value import Value
from pcot.xform import XFormType, xformtype, XFormException

logger = logging.getLogger(__name__)


def collectCameraData(node, img):
    """This first part of the code is called from perform(). It collects the data for the reflectance
    calculation and makes sure that the image is suitable (each band has one filter, all from the same
    camera, and that camera has reflectance data for the calibration target).

    It also collects the available calibration targets from the camera data which may lead to a
    chicken/egg scenario - perform() needs to run so that we know what targets are present and can set
    up the UI, but the UI needs to be set up before we can run perform() effectively.

    Collected data is stored in node.
    """
    # we need to get the filters from the image and make sure there's only one for each band
    filters = img.sources.getFiltersByBand()
    if len(filters) == 0:
        raise XFormException('DATA', 'image must have filter data to calibrate')
    if builtins.max([len(x) for x in filters]) != 1:
        raise XFormException('DATA', 'image must have a camera, and each band must have exactly one filter')
    # and get those single filters for each band
    filters = [next(iter(x)) for x in filters]

    # and then we need to make sure all the cameras on the filters are the same
    cameraset = set([x.camera_name for x in filters])
    if len(cameraset) != 1:
        raise XFormException('DATA', 'all bands must come from the same camera')
    # get the only member of that set
    camera = next(iter(cameraset))
    if camera is None:
        raise XFormException('DATA', 'image in "reflectance" appears to have no camera filters assigned')

    # and try to get the actual camera data
    camera = cameras.getCamera(camera)
    node.filters = filters
    node.camera = camera
    node.filter_index_by_name = {f.name: i for i, f in enumerate(filters)}


@dataclasses.dataclass
class ReflectancePoint:
    """A point on the reflectance plot. This is a tuple of two values: the known reflectance and the measured
    reflectance, both stored as SimpleValue objects. The patch name is also stored for labelling purposes.
    """
    known: SimpleValue
    measured: SimpleValue
    sample_count: int
    patch: str


@xformtype
class XFormReflectance(XFormType):
    """
    Given an image which has source data and a set of labelled ROIs
    (regions of interest), generate gradient and intercept values
    to correct the image to reflectance values.

    The ROIs must correspond to calibration target patches in the image.
    The calibration target can be selected by the user.

    The image must know what camera and filters it came from, and the camera
    must have filter information including nominal reflectances for each
    patch on that target.

    The **target angles**  are the theta (polar) and phi (azimuth) angles for incident light on
    the patch; the reflectance angle is fixed at 24 degrees theta and 0 degrees phi.

    Phi is measured clockwise from 0 at a line running from the centre of the PCT
    to the right, assuming the PCT is held with the two large patches at the top.

    The **filter angle** is the angle of transmission through the filter, with 0=straight through.


    The outputs are the gradient and intercept of the fit for each filter. All source
    data is removed, so it does not obscure image data in subsequent operations. The
    next operation should be an expr node performing out=(in-c)/m.
    """

    def __init__(self):
        super().__init__("reflectance", "calibration", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("m", Datum.NUMBER)
        self.addOutputConnector("c", Datum.NUMBER)

        self.params = TaggedDictType(
            # there might not be a calibration target because it's not valid for this image (or there's no image)
            target=("The calibration target to use", Maybe(str)),
            show_patches=("Show the patch names on the plot", bool, True),
            sep_plots=("Show the plots as separate small plots for each filter", bool, False),
            theta_target=("Theta (polar) angle of target (degs)", float, 0.0),
            phi_target=("Phi (azimuth) angle of target (degs)", float, 270.0),
            filter_angle=("Filter transmission angle (degs)", float, 0.0),

            # fudges; will probably remove
            zero_fudge=("Add an extra zero point", bool, False),
            simpler_data_fudge=("Force all points to have same number of pixels and same SD", bool, False),
        )

    def init(self, node):
        # no serialisation needed for this data.
        node.filter_to_plot = None
        node.filters = None
        node.camera = None
        # For each filter, there will be a list of points to plot. Each point will have
        # the known reflectance and the measured reflectance.
        node.points_per_filter = {}
        # there will also be the final fit - a dict of filtername to Fit object
        node.fits = {}

    def createTab(self, xform, window):
        return TabReflectance(xform, window)

    def perform(self, node):
        # read the image
        img = node.getInput(0, Datum.IMG)
        if img is None:
            raise XFormException('DATA', 'no image data')

        # collect reflectance data and check the image is valid (throws exception if not)
        try:
            collectCameraData(node, img)
        except cameras.CameraNotFoundException as e:
            ui.error(str(e))
            node.setOutput(0, Datum.null)
            node.setOutput(1, Datum.null)
            raise XFormException('DATA', str(e))

        if node.params.target is None:
            # select the default calibration target if possible
            targets = cameras.getReflectanceNames()
            if len(targets)==0:
                raise XFormException('DATA', 'no calibration targets available')
            node.params.target = targets[0]     # TODO - default reflectance target

        # get the reflectance object; may throw an exception if the target isn't found on this system
        reflectance = cameras.getReflectance(node.params.target)

        # we're going to store the points we need to fit in a list for each filter.
        points_per_filter: Dict[str, List[ReflectancePoint]] = {}

        # The way this works is slightly messy - when preparing the data, we iterate over ROIs (patches) and
        # then filters inside that. That means we only need to collect the ROI subimage once.
        # When we actually do the fit, we need to do the filters in the outer loop, with the patches collected
        # for each filter.

        for patch in reflectance.get_patches():
            # We need to extract the patch from the image. It will be one of the ROIs, and if it
            # isn't there we must disregard it - it may be that the calibration target detection is
            # not perfect. We can warn, though.
            roi = img.getROIByLabel(patch)

            if roi is None:
                continue

            if roi.bb() is None:
                raise XFormException("DATA","ROI has no BB")

            if roi.bb().size() == 0:
                continue   # only consider an ROI if it's non-zero in size

            subimg = img.subimage(roi=roi)  # get the part of the image covered by ROI
            # see ImageCube.getROIBadBands for how this works - it gets the bands in an image
            # for which all pixels have a BAD bit set.
            mask = ~subimg.fullmask(maskBadPixels=True)
            bad_bands = np.all(mask, axis=(0, 1))  # vector of booleans giving bad bands

            # get the masked data itself from the ROI
            means, stds = subimg.masked_all(maskBadPixels=True, noDQ=True)
            # split the data into bands - we need to work separately on each band.
            means = image.imgsplit(means)
            stds = image.imgsplit(stds)

            # get the known reflectance for each filter along with the filter, and
            # then the measured reflectance for each band.
            for filter in node.filters:
                filter_name = filter.name

                # get the band index for this filter - we have Filter items in node.filters
                band_index = node.filter_index_by_name.get(filter_name, None)
                if band_index is None:
                    # this filter is not in the image, so skip it
                    logger.debug(f"Filter {filter_name} not in image, skipping")
                    continue

                if bad_bands[band_index]:
                    # this band is bad for this ROI, so skip it
                    logger.debug(f"Band {band_index} is bad, skipping")
                    continue

                # flatten the means and sds and remove the masked pixels (we shouldn't really
                # need to do this but it aids debugging)

                band_means = means[band_index].compressed().flatten()
                band_stds = stds[band_index].compressed().flatten()

                # sanity check for no good pixels
                if len(band_means) == 0:
                    logger.debug(f"Band {band_index} has no good pixels in {patch}, skipping")
                    continue

                # now prepare plotting data
                measured_mean = np.mean(band_means)
                measured_std = pooled_sd(band_means, band_stds)

                if measured_std == 0:
                    # this band has no variance, so skip it - both because the data is probably duff,
                    # and because it makes NaN in the maths.
                    logger.debug(f"Band {band_index} has no variance, skipping")
                    continue

                # get the known data
                known_mean = reflectance.get_known_reflectance_for_filter(filter,patch,
                                                                          node.params.phi_target,
                                                                          node.params.theta_target,
                                                                          node.params.filter_angle)
                known_std = 0       # TODO get the STD of the known reflectance

                logger.debug(
                    f"Band {band_index} has measured {measured_mean}±{measured_std}, known {known_mean}±{known_std}")

                # create a data point for this filter / patch pairing

                point = ReflectancePoint(
                    SimpleValue(known_mean, known_std),
                    SimpleValue(measured_mean, measured_std),
                    band_means.size,
                    patch)

                if filter_name not in points_per_filter:
                    points_per_filter[filter_name] = []
                points_per_filter[filter_name].append(point)

        if len(points_per_filter) == 0:
            raise XFormException('DATA', 'no points - perhaps no patches found in image?')

        node.points_per_filter = points_per_filter  # stash for the UI

        # now we can do the fit on a per-filter basis.

        node.fits = {}
        for filter_name, points in points_per_filter.items():
            measured_list = [x.measured for x in points]
            known_list = [x.known for x in points]

            for rp in points:
                print(f"Processing {rp.patch} for {filter_name}")

            # FUDGE = Set the SD to a very small value. Can't set to zero because the maths blows up.
            if node.params.simpler_data_fudge:
                measured_list = [SimpleValue(m.mean, np.float32(0.0001)) for m in measured_list]

            # FUDGE = make sure it goes through zero.
            if node.params.zero_fudge:
                known_list.append(SimpleValue(np.float32(0.0), np.float32(0.0)))
                measured_list.append(SimpleValue(np.float32(0.0), np.float32(0.0001)))  # zero measured value

            f = pcot.calib.fit(known_list, measured_list)
            node.fits[filter_name] = f  # store the fit data so we can use it in the UI
            logger.debug(f"Filter {filter_name} has fit {f.m}±{f.sdm}x + {f.c}±{f.sdc}")

        # preset the outputs to a null (error)
        node.setOutput(0, Datum.null)
        node.setOutput(1, Datum.null)

        # assemble the output
        add_out_n = []
        add_out_u = []
        mul_out_n = []
        mul_out_u = []
        for f in node.filters:
            try:
                fit = node.fits[f.name]
            except KeyError:
                # this filter has no fit data, so skip it
                ui.log(
                    f"Filter {f.name} has no fit data! Is it correctly labelled in the source image and is it in the calibration data?")
                return
            add_out_n.append(fit.c)
            add_out_u.append(fit.sdc)
            mul_out_n.append(fit.m)
            mul_out_u.append(fit.sdm)
        # and set the output. We add the sources from the image, but modified as secondary.

        sources = img.sources.copy().visit(
            lambda sourceSet: sourceSet.visit(
                lambda source: source.setSecondaryName("reflectance target")
            ))

        node.setOutput(0, Datum(Datum.NUMBER, Value(np.array(mul_out_n), np.array(mul_out_u)), sources=sources))
        node.setOutput(1, Datum(Datum.NUMBER, Value(np.array(add_out_n), np.array(add_out_u)), sources=sources))


class TabReflectance(pcot.ui.tabs.Tab):
    def __init__(self, node, window):
        super().__init__(window, node, 'tabreflectance.ui')
        self.w.targetCombo.currentIndexChanged.connect(self.targetChanged)
        self.w.filterCombo.currentIndexChanged.connect(self.filterChanged)
        self.w.replot.clicked.connect(self.replot)
        self.w.showPatchesBox.checkStateChanged.connect(self.showPatchesStateChanged)
        self.w.sepPlotsBox.checkStateChanged.connect(self.sepPlotsBoxStateChanged)
        self.w.saveButton.clicked.connect(self.save)
        self.w.showMCButton.clicked.connect(self.showMCClicked)
        self.w.hideButton.clicked.connect(self.hideClicked)
        self.w.fudgesInfoButton.clicked.connect(self.showFudgesInfo)

        self.w.phiSpin.valueChanged.connect(self.phiChanged)
        self.w.thetaSpin.valueChanged.connect(self.thetaChanged)
        self.w.filterAngleSpin.valueChanged.connect(self.filterAngleChanged)
        self.w.recalcButton.clicked.connect(self.recalcButtonClicked)

        self.w.zeroFudgeBox.checkStateChanged.connect(self.zeroFudgeStateChanged)
        self.w.simplifyFudgeBox.checkStateChanged.connect(self.simplifyFudgeStateChanged)
        self.w.warningsTable.setColumnCount(2)

        self.w.fudgesInfoButton.setIcon(Icons.get("info"))

        self.nodeChanged()

    def save(self):
        self.w.mpl.save()

    def showFudgesInfo(self):
        showHelpDialog(self,"Fudges", """
        # Fudges
        
        These are mainly for debugging and truly vile data sets.
        
        If you are not dealing with either of those cases, please **don't**. 
        Even then, <font color='red'>**don't**</color>.
        
        If you decide to go ahead, ***tuum erit periculum.***
        
        * "Add zero points" adds a lot of points at the origin; the idea being to force the fit to go through
        the origin.
        * "Simplify data" makes all measured data have the same number of points and small variance.
        
        *Peidiwch â thynnu nythod cacwn ar eich ben.*
        """)

    def hideClicked(self):
        self.w.controls.setVisible(not self.w.controls.isVisible())
        self.setHideButtonText()

    def setHideButtonText(self):
        self.w.hideButton.setText(
            "Hide Controls" if self.w.controls.isVisible() else "Show Controls"
        )

    def changed(self):
        # when the node change is run, we need to clear the recalc button's style.
        super().changed()
        theme.setStaleStyle(self.w.recalcButton, False)

    def recalcButtonClicked(self):
        # recalculate; call changed() so that the new values are copied into the node and the node runs,
        # then replot the curves. In that order, or else the plot will be from the old data.
        self.changed()
        self.replot()

    def mustRecalc(self):
        # if an angle etc. changed we need to recalculate the node and all its children  - typically slow,
        # so we make it a user action, indicating that necessity by making the recalc button red.
        theme.setStaleStyle(self.w.recalcButton, True)

    def showMCClicked(self):
        # open a dialog containing a single text edit box with the gradient and intercept values

        m = self.node.getOutput(0, Datum.NUMBER)
        c = self.node.getOutput(1, Datum.NUMBER)
        # construct a Table and pass it to a TableDialog
        if m is not None and c is not None:
            table = Table()
            for i, f in enumerate(self.node.filters):
                table.newRow(f.name)
                table.add("Filter", f.name)
                table.add("CWL",int(f.cwl))
                table.add("Gradient", m[i])
                table.add("Intercept", c[i])

            dialog = TableDialog("Gradients and intercepts", table)
            dialog.exec()

    def targetChanged(self, i):
        self.mark()
        self.node.params.target = self.w.targetCombo.currentText()
        self.mustRecalc()

    def phiChanged(self, i):
        self.mark()
        self.node.params.phi_target = self.w.phiSpin.value()
        self.mustRecalc()

    def thetaChanged(self, i):
        self.mark()
        self.node.params.theta_target = self.w.thetaSpin.value()
        self.mustRecalc()

    def filterAngleChanged(self, i):
        self.mark()
        self.node.params.filter_angle = self.w.filterAngleSpin.value()
        self.mustRecalc()

    def filterChanged(self, i):
        # data unchanged, no need to mark or call changed().
        self.node.filter_to_plot = self.w.filterCombo.currentText()
        self.markReplotReady()

    def showPatchesStateChanged(self, state):
        # data unchanged, no need to mark or call changed().
        self.node.params.show_patches = state == Qt.CheckState.Checked
        self.markReplotReady()

    def sepPlotsBoxStateChanged(self, state):
        self.node.params.sep_plots = state == Qt.CheckState.Checked
        self.markReplotReady()

    def zeroFudgeStateChanged(self, state):
        self.mark()
        self.node.params.zero_fudge = state == Qt.CheckState.Checked
        self.changed()

    def simplifyFudgeStateChanged(self, state):
        self.mark()
        self.node.params.simpler_data_fudge = state == Qt.CheckState.Checked
        self.changed()

    def onNodeChanged(self):
        self.markReplotReady()
        # get the valid targets from the image - the camera data will have this.
        with SignalBlocker(self.w.targetCombo):
            self.w.targetCombo.clear()
            names = cameras.getReflectanceNames()
            self.w.targetCombo.addItems(names)
            if self.node.params.target in cameras.getReflectanceNames():
                self.w.targetCombo.setCurrentIndex(names.index(self.node.params.target))
        # populate the filter combo box with the filters from the image
        filter_names = None
        with SignalBlocker(self.w.filterCombo):
            self.w.filterCombo.clear()
            if self.node.filters:
                filter_names = [f.name for f in self.node.filters]
                self.w.filterCombo.addItem("ALL")
                self.w.filterCombo.addItems(filter_names)
                try:
                    # +1 here because of the ALL value
                    self.w.filterCombo.setCurrentIndex(filter_names.index(self.node.filter_to_plot) + 1)
                except ValueError:
                    # this filter is not in the image?
                    ui.log(f"Filter {self.node.filter_to_plot} not in image, using ALL")
                    self.w.filterCombo.setCurrentIndex(0)
                    self.node.filter_to_plot = self.w.filterCombo.currentText()

        # reset and populate the warnings table

        t = self.w.warningsTable
        t.clear()
        t.setHorizontalHeaderLabels(["filter","warning"])
        hdr = t.horizontalHeader()
        hdr.setSectionResizeMode(0,QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1,QtWidgets.QHeaderView.ResizeMode.Stretch)

        row=0
        if self.node.fits and filter_names is not None:
            for i,fname in enumerate(filter_names):
                fit = self.node.fits.get(fname)
                if fit.warning is not None:
                    t.insertRow(row)
                    t.setItem(row,0,QtWidgets.QTableWidgetItem(fname))
                    t.setItem(row,1,QtWidgets.QTableWidgetItem(fit.warning))
                    bg, fg = theme.warningItemColours()
                    t.item(row,1).setBackground(bg)
                    t.item(row,1).setForeground(fg)
                    row+=1


        self.w.showPatchesBox.setChecked(self.node.params.show_patches)
        self.w.sepPlotsBox.setChecked(self.node.params.sep_plots)

        self.w.zeroFudgeBox.setChecked(self.node.params.zero_fudge)
        self.w.simplifyFudgeBox.setChecked(self.node.params.simpler_data_fudge)

        self.w.phiSpin.setValue(self.node.params.phi_target)
        self.w.thetaSpin.setValue(self.node.params.theta_target)
        self.w.filterAngleSpin.setValue(self.node.params.filter_angle)

    def markReplotReady(self):
        """make the replot button red"""
        theme.setStaleStyle(self.w.replot, True)

    @staticmethod
    def set_axis_data(ax, sep_plots=False):
        ax.cla()
        if not sep_plots:
            ax.set_xlabel("Known reflectance")
            ax.set_ylabel("Measured reflectance")
        else:
            ax.tick_params(labelsize=6)

            # we don't generally do this.
            # ax.set_ylim(bottom=0)
            # ax.set_xlim(left=0)

        # move the axes to pass through the origin
        ax.spines['left'].set_position('zero')
        ax.spines['right'].set_color('none')
        ax.yaxis.tick_left()
        ax.spines['bottom'].set_position('zero')
        ax.spines['top'].set_color('none')
        ax.xaxis.tick_bottom()

    def replot_sep_plots(self):
        plotct = 1
        # clear all figures
        self.w.mpl.fig.clf()
        self.w.mpl.fig.subplots_adjust(hspace=0.2)
        for filter in self.node.filters:
            filter_name = filter.name
            ax = self.w.mpl.fig.add_subplot(3, 4, plotct)
            self.set_axis_data(ax,sep_plots=True)
            plotct += 1

            points = self.node.points_per_filter.get(filter_name, None)
            fit = self.node.fits.get(filter_name, None)

            if points is None:
                ui.log(f"No points of data for filter {filter_name}")
                continue
            if fit is None:
                ui.log(f"No fit data for filter {filter_name}")
                continue

            # separate out the data
            points = [dataclasses.astuple(p) for p in points]
            known, measured, sample_counts, patches = zip(*points)

            known_mean = [x.mean for x in known]
            measured_mean = [x.mean for x in measured]
            known_std = [x.std for x in known]
            measured_std = [x.std for x in measured]

            # plot
            if fit:
                ax.axline((0, fit.c), slope=fit.m)
            # ax.plot(known, measured, '+', color=colname, label=band)
            ax.errorbar(known_mean, measured_mean, yerr=measured_std, xerr=known_std, label=filter_name, fmt='x')

            # point labelling: don't do this if we're plotting all bands or it's turned off
            cwl = self.node.camera.getFilter(filter_name).cwl
            ax.set_title(f"Fit for {filter_name} {int(cwl)}: m={fit.m:0.3f}, c={fit.c:0.3f}",fontsize=6)
            for i, patch in enumerate(patches):
                # plot the patch name and the measured value at the point
                ax.annotate(f"{patch}\n{measured_mean[i]:.2f}±{measured_std[i]:.2f}",
                            (known_mean[i], measured_mean[i]), fontsize=5)
        self.w.mpl.draw()

    def replot(self):
        theme.setStaleStyle(self.w.replot, False)
        # the MPL widget creates a default subplot, let's clear it...
        self.w.mpl.fig.clf()
        if self.node.params.sep_plots:
            self.replot_sep_plots()
            return

        # and here, reset the plot and recreate the subplot
        self.w.mpl.clear()

        ax = self.w.mpl.ax
        self.set_axis_data(ax)

        if self.node.filter_to_plot is None or self.node.filter_to_plot == "ALL":
            bands = [f.name for f in self.node.filters]
        else:
            bands = [self.node.filter_to_plot]

        col = 0  # colour index
        for band in bands:
            # this will be (known_mean, known_std, measured_mean, measured_std)
            points = self.node.points_per_filter.get(band, None)
            fit = self.node.fits.get(band, None)

            if points is None:
                ui.log(f"No points of data for filter {band}")
                continue
            if fit is None:
                ui.log(f"No fit data for filter {band}")
                continue
            # separate out the data
            points = [dataclasses.astuple(p) for p in points]
            known, measured, sample_counts, patches = zip(*points)

            known_mean = [x.mean for x in known]
            measured_mean = [x.mean for x in measured]
            known_std = [x.std for x in known]
            measured_std = [x.std for x in measured]

            # plot
            colname = f"C{col}"
            col += 1
            if fit:
                ax.axline((0, fit.c), slope=fit.m, color=colname)
            # ax.plot(known, measured, '+', color=colname, label=band)
            cwl = self.node.camera.getFilter(band).cwl
            ax.errorbar(known_mean, measured_mean, yerr=measured_std, xerr=known_std,
                        label=f"{band} {int(cwl)}nm", fmt='x',
                        color=colname)

            # point labelling: don't do this if we're plotting all bands or it's turned off
            if len(bands) == 1 and self.node.params.show_patches:
                ax.set_title(f"Fit for {band} {int(cwl)}: m={fit.m:0.3f}, c={fit.c:0.3f}")
                for i, patch in enumerate(patches):
                    # plot the patch name and the measured value at the point
                    ax.annotate(f"{patch}\n{measured_mean[i]:.2f}±{measured_std[i]:.2f} (n={sample_counts[i]})",
                                (known_mean[i], measured_mean[i]), fontsize=8)

        if len(bands) > 1:
            ax.legend(loc="lower right")

        self.w.mpl.draw()
        theme.setStaleStyle(self.w.replot, False)
