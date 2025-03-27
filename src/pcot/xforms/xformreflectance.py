import builtins
import logging

import numpy as np

import pcot.ui.tabs
from pcot import config, cameras
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

    if node.params.target and node.params.target not in node.calib_targets:
        raise XFormException('DATA', 'target not in calibration data')


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
        node.points_per_filter = {}

        for patch, filter_dicts in data.items():
            # We need to extract the patch from the image. It will be one of the ROIs, and if it
            # isn't there we must disregard it - it may be that the calibration target detection is
            # not perfect. We can warn, though.
            roi = img.getROIByLabel(patch)

            if roi:
                subimg = img.subimage(roi=roi)  # get the part of the image covered by ROI
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
                    # get the data for this band
                    measured_mean = np.mean(means[band_index])
                    measured_std = pooled_sd(means[band_index], stds[band_index])
                    # and find the mean and pooled SD of that
                    logger.debug(
                        f"Band {band_index} has measured {measured_mean}±{measured_std}, known {known_mean}±{known_std}")
                    point = (known_mean, known_std, measured_mean, measured_std)
                    if filter_name not in node.points_per_filter:
                        node.points_per_filter[filter_name] = []
                    node.points_per_filter[filter_name].append(point)


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
            self.w.filterCombo.addItems([x.name for x in self.node.filters])
            self.w.filterCombo.setCurrentIndex(self.node.filters.index(self.node.filter_to_plot))

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def replot(self):
        # this will be (known_mean, known_std, measured_mean, measured_std)
        band = self.node.filter_to_plot
        points = self.node.points_per_filter.get(band, [[], [], [], []])

        # separate out the data
        known, known_std, measured, measured_std = zip(*points)

        ax = self.w.mpl.ax
        ax.cla()
        ax.set_xlabel("Known reflectance (nm)")
        ax.set_ylabel("Measured reflectance (nm)")
        ax.plot(known, measured, '+-r')
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")
