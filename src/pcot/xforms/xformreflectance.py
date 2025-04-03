import builtins
import logging
import dataclasses
from typing import Tuple, List, Dict

import numpy as np

import pcot.ui.tabs
from pcot import config, cameras, ui
from pcot.calib import SimpleValue, fit
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe
from pcot.utils import SignalBlocker, image
from pcot.utils.maths import pooled_sd
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
        raise XFormException('DATA', 'image must have filter data to get flats')
    if builtins.max([len(x) for x in filters]) != 1:
        raise XFormException('DATA', 'each band must have exactly one filter')
    # and get those single filters for each band
    filters = [next(iter(x)) for x in filters]

    # and then we need to make sure all the cameras on the filters are the same
    cameraset = set([x.camera_name for x in filters])
    if len(cameraset) != 1:
        raise XFormException('DATA', 'all bands must come from the same camera')
    # get the only member of that set
    camera = next(iter(cameraset))
    # and try to get the actual camera data
    camera = cameras.getCamera(camera)

    # now we can store the calibration targets this camera knows about
    node.reflectance_data = camera.getReflectances()
    node.calib_targets = list(node.reflectance_data.keys()) if node.reflectance_data else []
    node.filters = filters
    node.filter_names = [f.name for f in filters]

    if node.params.target and node.params.target not in node.calib_targets:
        raise XFormException('DATA', 'target not in calibration data')


@dataclasses.dataclass
class ReflectancePoint:
    """A point on the reflectance plot. This is a tuple of (known, known_sd, measured, measured_sd)"""
    known: float
    known_sd: float
    measured: float
    measured_sd: float
    point: SimpleValue  # this is all the measured data for the point - every pixel
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
    """

    def __init__(self):
        super().__init__("reflectance", "calibration", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("mul", Datum.NUMBER)
        self.addOutputConnector("add", Datum.NUMBER)

        self.params = TaggedDictType(
            # there might not be a calibration target because it's not valid for this image (or there's no image)
            target=("The calibration target to use", Maybe(str))
        )

    def init(self, node):
        # no serialisation needed for this data.
        node.filter_to_plot = None
        node.calib_targets = []
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
        collectCameraData(node, img)

        if len(node.calib_targets) == 0:
            raise XFormException('DATA', 'no calibration targets available')
        elif len(node.calib_targets) == 1 or node.params.target is None:
            # there's only one target available, use it. Or there's no target set, so use the first one.
            node.params.target = node.calib_targets[0]

        # collect the known reflectance values from the calibration data
        if node.params.target not in node.reflectance_data:
            raise XFormException('DATA', f"target '{node.params.target}' not in calibration data")
        # data will be {patchname: {filtername: (mean, std)}}. This is annoying, but makes sense.
        data = node.reflectance_data[node.params.target]

        # we're going to store the points we need to fit in a list for each filter.
        points_per_filter: Dict[str, List[ReflectancePoint]] = {}

        # The way this works is slightly messy - when preparing the data, we iterate over ROIs (patches) and
        # then filters inside that. That means we only need to collect the ROI subimage once.
        # When we actually do the fit, we need to do the filters in the outer loop, with the patches collected
        # for each filter.

        for patch, filter_dicts in data.items():
            # We need to extract the patch from the image. It will be one of the ROIs, and if it
            # isn't there we must disregard it - it may be that the calibration target detection is
            # not perfect. We can warn, though.
            roi = img.getROIByLabel(patch)

            if roi and roi.bb().size() > 0:  # only consider an ROI if it's non-zero in size
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
                for filter_name, (known_mean, known_std) in filter_dicts.items():
                    # get the band index for this filter - we have Filter items in node.filters
                    for band_index, band in enumerate(node.filters):
                        if band.name == filter_name:
                            break
                    else:
                        # this filter is not in the image
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
                        logger.debug(f"Band {band_index} has no good pixels, skipping")
                        continue

                    # now prepare plotting data
                    measured_mean = np.mean(band_means)
                    measured_std = pooled_sd(band_means, band_stds)
                    logger.debug(
                        f"Band {band_index} has measured {measured_mean}±{measured_std}, known {known_mean}±{known_std}")

                    # create a data point for this filter / patch pairing
                    point = ReflectancePoint(known_mean, known_std, measured_mean, measured_std,
                                             SimpleValue(band_means, band_stds),
                                             patch)

                    if filter_name not in points_per_filter:
                        points_per_filter[filter_name] = []
                    points_per_filter[filter_name].append(point)

        if len(points_per_filter) == 0:
            raise XFormException('DATA', 'no points - perhaps no patches found in image?')

        # now we can do the fit on a per-filter basis.

        node.fits = {}
        for filter_name, points in points_per_filter.items():
            point_list = [x.point for x in points]
            known_list = [x.known for x in points]
            # warning a bit weird here - point_list is a List[SimpleValue] and the warning is a lie.
            node.fits[filter_name] = fit(known_list, point_list)

        node.points_per_filter = points_per_filter


class TabReflectance(pcot.ui.tabs.Tab):
    def __init__(self, node, window):
        super().__init__(window, node, 'tabreflectance.ui')
        self.w.targetCombo.currentIndexChanged.connect(self.targetChanged)
        # populate the target combo box
        self.w.filterCombo.currentIndexChanged.connect(self.filterChanged)
        # populating the filter combo box with filters from the input image is done
        # in the nodeChanged method
        self.w.replot.clicked.connect(self.replot)
        self.nodeChanged()

    def targetChanged(self, i):
        self.mark()
        self.node.params.target = self.w.targetCombo.currentText()
        self.changed()

    def filterChanged(self, i):
        self.mark()
        self.node.filter_to_plot = self.w.filterCombo.currentText()
        self.changed()

    def onNodeChanged(self):
        self.markReplotReady()
        # get the valid targets from the image - the camera data will have this.
        with SignalBlocker(self.w.targetCombo):
            self.w.targetCombo.clear()
            self.w.targetCombo.addItems(self.node.calib_targets)
            if self.node.params.target in self.node.calib_targets:
                self.w.targetCombo.setCurrentIndex(self.node.calib_targets.index(self.node.params.target))
        # populate the filter combo box with the filters from the image
        with SignalBlocker(self.w.filterCombo):
            self.w.filterCombo.clear()
            self.w.filterCombo.addItems(self.node.filter_names)
            try:
                self.w.filterCombo.setCurrentIndex(self.node.filter_names.index(self.node.filter_to_plot))
            except ValueError:
                # this filter is not in the image?
                ui.log(f"Filter {self.node.filter_to_plot} not in image, using first filter")
                self.w.filterCombo.setCurrentIndex(0)
                self.node.filter_to_plot = self.w.filterCombo.currentText()

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def replot(self):
        # this will be (known_mean, known_std, measured_mean, measured_std)
        band = self.node.filter_to_plot
        points = self.node.points_per_filter.get(band, None)
        fit = self.node.fits.get(band,None)

        if points is None:
            ui.log(f"No data for filter {band}")
            return

        # separate out the data
        points = [dataclasses.astuple(p) for p in points]
        known, known_std, measured, measured_std, _, patches = zip(*points)

        ax = self.w.mpl.ax
        ax.cla()
        ax.set_xlabel("Known reflectance (nm)")
        ax.set_ylabel("Measured reflectance (nm)")
        if fit:
            ax.axline((0, fit.c), slope=fit.m, color='blue', label='fit')
        ax.plot(known, measured, '+r')
        ax.set_ylim(bottom=0)
        ax.set_xlim(left=0)
        for i, patch in enumerate(patches):
            ax.annotate(f"{patch}\n{measured[i]:.2f}", (known[i], measured[i]), fontsize=8)
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")
