import cv2 as cv
import numpy as np

from pcot import ui


def debayer(img, algorithm='bilinear', pattern='gb'):
    """Debayering. Takes a 16bit 2D Numpy array, an algorithm and a debayering pattern string. Only the
    first band of a multi-band image will be used."""
    m = None
    pattern = pattern.lower()
    algorithm = algorithm.lower()
    if pattern == 'bg':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerBG2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerBG2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerBG2RGB_EA
    elif pattern == 'gb':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerGB2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerGB2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerGB2RGB_EA
    elif pattern == 'rg':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerRG2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerRG2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerRG2RGB_EA
    elif pattern == 'gr':
        if algorithm == "bilinear":
            m = cv.COLOR_BayerGR2RGB
        elif algorithm == "vng":
            m = cv.COLOR_BayerGR2RGB_VNG
        elif algorithm == "ea":
            m = cv.COLOR_BayerGR2RGB_EA

    if not m:
        raise ValueError(f"debayering - algorithm '{algorithm}' or Bayer pattern '{pattern}' not found")

    if len(img.shape) != 2:
        img = img[:, :, 0]  # if there is more than one band, use only the first

    if algorithm == 'vng' and img.dtype == np.uint16:
        # we need to downsample to 8 bits
        img = (img>>8).astype(np.uint8)
        ui.log("Warning - VNG requires downsampling to 8 bits")

    return cv.demosaicing(img, m)
