"""
This file tests that we can filter out ROIs entirely consisting of bad pixels.
"""
import numpy as np

from pcot import dq
from pcot.imagecube import ImageCube
from pcot.rois import ROICircle, ROIRect


def test_filter_bad_roi_zero_size():
    # Create an imagecube with 4 bands
    ic = ImageCube(np.zeros((100, 100, 4), dtype=np.float32))

    # add a circular ROI
    ic.rois.append(ROICircle(40, 40, 10, label="good-circ"))
    # and a rectangular one
    ic.rois.append(ROIRect(rect=(60, 60, 20, 20), label="good-rect"))

    # add a zero-sized one
    ic.rois.append(ROIRect(rect=(0, 0, 0, 0), label="bad-rect"))

    # if we filter out the bad ones, we should be left with 2
    good = ic.filterBadROIs()
    labels = [roi.label for roi in good]
    assert "good-circ" in labels
    assert "good-rect" in labels
    assert "bad-rect" not in labels


def test_filter_bad_roi_all_pixels_bad():
    # Create an imagecube with 4 bands
    ic = ImageCube(np.zeros((100, 100, 4), dtype=np.float32))

    # create a circular ROI and use it to set bad pixels in the image
    roi_to_set = ROICircle(30,30, 20)
    ic.rois.append(roi_to_set)
    ss = ic.subimage()   # we are editing the subimage - relies on the returned value holding slices, not copy.
    dqs = ss.maskedDQ(maskBadPixels=True)
    dqs |= dq.BAD


    # add a circular ROI
    ic.rois.append(ROICircle(40, 40, 10, label="good-circ"))
    # and a rectangular one
    ic.rois.append(ROIRect(rect=(60, 60, 20, 20), label="good-rect"))

    # add another circle
    ic.rois.append(ROICircle(40, 40, 10, label="bad-circ"))

    # if we filter out the bad ones, we should be left with 2
    good = ic.filterBadROIs()
    labels = [roi.label for roi in good]
    assert "good-circ" in labels
    assert "good-rect" in labels
    assert "bad-rect" not in labels
