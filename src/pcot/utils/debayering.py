import cv2 as cv
import numpy as np

from pcot import ui
from pcot.utils.demosaicing.malvar import demosaicing_CFA_Bayer_Malvar2004
from pcot.utils.demosaicing.menon import demosaicing_CFA_Bayer_DDFAPD


def debayer_cv(img, algorithm='bilinear', pattern='RGGB'):
    m = None
    pattern = pattern.upper()
    algorithm = algorithm.lower()

    # OK. OpenCV has a really weird naming convention for demosaicing:
    # https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html#color_convert_bayer

    # Paraphrasing a bit:
    # "The two letters XX in the conversion constant CV_BayerXX_2RGB indicates the particular pattern type.
    # These are components from the second row, second and third columns, respectively"

    # But we're not using that because it ALSO supports the "classical" tl,tr,bl,br naming scheme.

    if pattern == 'BGGR':       # BGGR ->
        if algorithm == "bilinear":
            m = cv.COLOR_BayerBGGR2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerBGGR2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerBGGR2RGB_EA
    elif pattern == 'GBRG':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerGBRG2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerGBRG2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerGBRG2RGB_EA
    elif pattern == 'RGGB':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerRGGB2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerRGGB2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerRGGB2RGB_EA
    elif pattern == 'GRBG':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerGRBG2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerGRBG2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerGRBG2RGB_EA

    if not m:
        raise ValueError(f"debayering - algorithm '{algorithm}' or Bayer pattern '{pattern}' not found")

    img = (img * 65535.0).astype(np.uint16) # 16 bit img needed
    if algorithm == 'vng' and img.dtype == np.uint16:
        # we need to downsample to 8 bits
        img = (img>>8).astype(np.uint8)
        out = cv.demosaicing(img, m)
        out = out.astype(np.float32) / 256.0
        ui.log("Warning - VNG requires downsampling to 8 bits")
    else:
        out =  cv.demosaicing(img, m)
        out = out.astype(np.float32) / 65535.0

    return out


def debayer(img, algorithm='bilinear', pattern='GBRG'):
    """Debayering. Takes a 16bit 2D Numpy array, an algorithm and a debayering pattern string. Only the
    first band of a multi-band image will be used."""

    pattern = pattern.upper()
    algorithm = algorithm.lower()

    if len(img.shape) != 2:
        img = img[:, :, 0]  # if there is more than one band, use only the first

    if algorithm == 'mhc':
        return demosaicing_CFA_Bayer_Malvar2004(img, pattern)
    elif algorithm == 'menon' or algorithm == 'ddfapd':
        return demosaicing_CFA_Bayer_DDFAPD(img, pattern)
    else:
        return debayer_cv(img, algorithm, pattern)
