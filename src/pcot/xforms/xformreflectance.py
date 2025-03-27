import builtins

import pcot.ui.tabs
from pcot import config, cameras
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XFormException


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
        node.filter_to_plot = 0
        node.calib_targets = []
        # For each filter, there will be a list of points to plot. Each point will have
        # the known reflectance and the measured reflectance.
        node.points_per_filter = []

    def createTab(self, xform, window):
        return TabReflectance(xform, window)

    def perform(self, node):
        # read the image
        img = node.getInput(0, Datum.IMG)
        if img is None:
            raise XFormException('DATA', 'no image data')

        # collect reflectance data and check the image is valid (throws exception if not)
        collectCameraData(node, img)

        # collect the known reflectance values from the calibration data
        if node.params.target not in node.reflectance_data:
            raise XFormException('DATA', f"target '{node.params.target}' not in calibration data")
        # data will be {patchname: {filtername: (mean, std)}}. This is annoying, but makes sense.
        data = node.reflectance_data[node.params.target]

        # we're going to produce a dictionary of filter: [(known, measured)] where each tuple is a patch.

        for patch, filter_dicts in data.items():
            # We need to extract the patch from the image. It will be one of the ROIs, and if it
            # isn't there we must disregard it - it may be that the calibration target detection is
            # not perfect. We can warn, though.
            roi = img.rois.getROIByLabel(patch)
            if roi:
                subimg = img.subimage(roi)  # get the part of the image covered by ROI
                # get the masked data itself from the ROI
                means, stds = subimg.masked_all(maskBadPixels=True, noDQ=True)
                # split the data into bands

                # get the known reflectance for each filter along with the filter..
                for filter_name, (known_mean, known_std) in filter_dicts.items():
                    # now we need to get the measured reflectance for this filter
                    pass #todo








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
        self.node.filter_to_plot = i
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
            self.w.filterCombo.setCurrentIndex(self.node.filter_to_plot)

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def replot(self):
        ax = self.w.mpl.ax
        ax.cla()
        ax.set_xlabel("Known reflectance (nm)")
        ax.set_ylabel("Measured reflectance (nm)")
        ax.plot([0, 1], [0, 1], '+-r')
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")
