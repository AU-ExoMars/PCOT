"""
This file tests that we can filter out ROIs entirely consisting of bad pixels.
"""
import numpy as np

from pcot.imagecube import ImageCube
from pcot.rois import ROICircle, ROIRect


def test_filter_bad_rois():
    # Create an imagecube with 4 bands
    ic = ImageCube(np.zeros((100, 100, 4), dtype=np.float32))

    # add a circular ROI
    # ic.rois.append(ROICircle(40, 40, 10, label="good-circ"))
    # and a rectangular one
    # ic.rois.append(ROIRect(rect=(60, 60, 20, 20), label="good-rect"))

    # add a zero-sized one
    ic.rois.append(ROIRect(rect=(0, 0, 0, 0), label="bad-rect"))

    # if we filter out the bad ones, we should be left with 2
    good = ic.filterBadROIs()
    labels = [roi.label for roi in good]
    assert "good-circ" in labels
    assert "good-rect" in labels
    assert "bad-rect" not in labels
