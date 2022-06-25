import cv2 as cv
import numpy as np

from pcot.datum import Datum
from pcot.utils import image
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage

# perform equalisation with a mask. Unfortunately cv.equalizeHist doesn't
# support masks.
# Takes a single-channel numpy array 
# and a single-channel mask of booleans

BINS = 2000


def equalize(img, mask):
    img = np.ma.masked_array(img, mask=~mask)
    mask = mask.astype(np.ubyte)
    # clip masked image
    img[img > 1] = 1
    img[img < 0] = 0

    # algorithm source: https://docs.opencv.org/master/d5/daf/tutorial_py_histogram_equalization.html
    # get histogram; N bins in range 0-1. Set the weight of all unmasked
    # pixels to zero so they don't get counted.

    hist, bins = np.histogram(img, BINS, weights=mask, range=[0, 1])

    # work out the cumulative dist. function and normalize it
    cdf = hist.cumsum()
    # cdf_normalized = cdf * float(hist.max()) / cdf.max()

    # get a masked array, omitting zeroes, and use it to construct
    # a lookup table for old to new intensities
    cdf_m = np.ma.masked_equal(cdf, 0)
    cdf_m = (cdf_m - cdf_m.min()) / (cdf_m.max() - cdf_m.min())
    cdf = np.ma.filled(cdf_m, 0)
    # convert the image to effectively a lookup table - each pixel now indexes into
    # the CDF for that level
    i2 = (img * (BINS - 1)).astype(np.int32)
    # and apply it to the masked region of the image
    np.putmask(img, mask, cdf[i2].astype(np.float32))


@xformtype
class XformHistEqual(XFormType):
    """
    Perform histogram equalisation on all channels of the image separately. Honours ROIs.
    Currently set to 2000 bins, but I may add a control for that."""

    def __init__(self):
        super().__init__("histequal", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.hasEnable = True

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            # can't equalize a non-existent image!
            out = None
        elif not node.enabled:
            out = img
        else:
            img = img.copy()  # act always on a copy
            # first extract the ROI subimage; the rectangle which
            # contains the ROIS and a mask we should work on
            subimage = img.subimage()

            # now we need to perform equalisation on just the pixels
            # in the mask! For this operation it's a bit hairy, because
            # the nice OpenCV equalizeHist function doesn't do masks.
            # So the equalize() function above does that.

            # deal with 3-channel and 1-channel images
            if img.channels == 1:
                equalized = subimage.img.copy()
                equalize(equalized, subimage.mask)
            else:
                lst = [x.copy() for x in image.imgsplit(subimage.img)]
                for band in lst:
                    equalize(band, subimage.mask)
                equalized = image.imgmerge(lst)

            # make a copy of the image and paste the modified version of the subimage into it
            out = img.modifyWithSub(subimage, equalized)
        if out is not None:
            out.setMapping(node.mapping)
        node.out = Datum(Datum.IMG, out)
        node.setOutput(0, node.out)
