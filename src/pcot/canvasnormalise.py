"""Image normalisation stuff for canvases.
This takes an image and an RGB image and generates a normalised RGB image. It can't just produce
an RGB image because the incoming image might be "premapped" by another node.

It will also:
    - only consider a rectangle of the image if required
    - TODO ignore "bad" pixels

Modes and their actions:
    NormSeparately: each rgb channel is normalised separately
    NormToRGB: each rgb channel is normalised to the range of RGB image's bands
    NormToImg: each rgb channel is normalised to the range all bands in the image
    NormNone: nothing is done

A boolean flag determines if the normalisation range is for the cropped image or the entire image.
"""

from typing import Optional, Tuple
import numpy as np
from pcot.imagecube import ImageCube

# normalisation modes
from pcot.utils.image import imgsplit, imgmerge

NormToRGB = 0  # normalise to visible RGB bands' range
NormToImg = 1  # normalise to entire image's range
NormSeparately = 2  # normalise each band separately


def getimg(img: np.ndarray, rect: Optional[Tuple[int, int, int, int]]):
    """Cut out part of an image, or just leave it unchanged if there is no part to cut"""
    if rect is not None:
        x, y, w, h = rect
        return img[y:y + h, x:x + w]
    else:
        return img


def normOrZero(img, mn, mx):
    """returns normalised copy of image or zeros"""
    if mx > mn:
        return (img - mn) / (mx - mn)
    else:
        return np.zeros(np.shape(img), dtype=img.dtype)


def canvasNormalise(img: ImageCube,
                    rgbCropped: np.ndarray,
                    rgbUncropped: np.ndarray,
                    normMode: int,
                    normToCropped: bool,
                    rect: Optional[Tuple[int, int, int, int]]) -> np.ndarray:
    """
    This does normalisation for the canvas. The parameter list may seem rather eccentric, but this
    set of parameters helps things run more smoothly with fewer copies and cuts.
    Arguments:
        img: image cube for entire image, all channels, not cropped
        rgbCropped: RGB numpy image array, cropped to view
        rgbUncropped: uncropped RGB image array (need this for normToEntireImage)
        normMode: see above
        normToCropped: do we normalise to he range of the entire image or just the cropped section?
        rect: rectangle we are 'cutting' which may be None. Only this range is considered.
    """
    if normMode == NormSeparately:
        # process each band in the cropped image separately
        bands = []
        for normband, imageband in zip(imgsplit(rgbCropped if normToCropped else rgbUncropped), imgsplit(rgbCropped)):
            mn = np.min(normband)
            mx = np.max(normband)
            bands.append(normOrZero(imageband, mn, mx))
        out = imgmerge(bands)
    elif normMode == NormToRGB:  # we're normalising to the entire cropped image
        x = rgbCropped if normToCropped else rgbUncropped
        mn = np.min(x)  # so we get the normalisation range from there
        mx = np.max(x)
        out = normOrZero(rgbCropped, mn, mx)
    elif normMode == NormToImg:  # now normalising to all bands
        if normToCropped:
            # crop if required
            x, y, w, h = rect
            img = img[y:y + h, x:x + w]
        mn = np.min(img)  # so we get the normalisation range from there
        mx = np.max(img)
        out = normOrZero(rgbCropped, mn, mx)
    else:
        out = rgbCropped  # otherwise we leave the RGB unchanged

    return out
