"""Image normalisation stuff for canvases.
This takes an image and an RGB image and generates a normalised RGB image. It can't just produce
an RGB image because the incoming image might be "premapped" by another node.

It will also:
    - only consider a rectangle of the image if one is provided (for canvas zooming)
    - TODO ignore "bad" pixels

Modes and their actions:
    NormSeparately: each rgb channel is normalised separately
    NormToRGB: each rgb channel is normalised to the range of all the RGB image's channels
    NormToImg: each rgb channel is normalised to the range of the entire image
    NormNone: nothing is done,
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
                    normMode: int,
                    rect: Optional[Tuple[int, int, int, int]]) -> np.ndarray:
    """
    Arguments:
        img: image cube for entire image, all channels, not cropped
        rgbCropped: RGB numpy array, cropped to view
        normMode: see above
        rect: rectangle we are 'cutting' which may be None. Only this range is considered.
    """
    if normMode == NormSeparately:
        bands = []
        for x in imgsplit(rgbCropped):  # process each band in the cropped image separately
            mn = np.min(x)
            mx = np.max(x)
            bands.append(normOrZero(x, mn, mx))
        out = imgmerge(bands)
    elif normMode == NormToRGB:  # we're normalising to the entire cropped image
        mn = np.min(rgbCropped)  # so we get the normalisation range from there
        mx = np.max(rgbCropped)
        out = normOrZero(rgbCropped, mn, mx)
    elif normMode == NormToImg:  # now normalising to all bands
        img = getimg(img, rect)  # remember, img is not cropped.
        mn = np.min(img)  # so we get the normalisation range from there
        mx = np.max(img)
        out = normOrZero(rgbCropped, mn, mx)
    else:
        out = rgbCropped  # otherwise we leave the RGB unchanged

    return out
