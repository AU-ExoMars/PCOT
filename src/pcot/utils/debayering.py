import cv2 as cv
import numpy as np
from scipy import ndimage

from pcot import ui


def debayer_cv(img, algorithm='bilinear', pattern='gb'):
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


def debayer_mhc(img, pattern):
    """Malvar/He/Cutler"""
    if img.ndim != 2:
        raise ValueError("Input must be a 2D Bayer pattern image.")

    # This work comes from here:
    # https://github.com/brandondube/prysm/blob/a973b18bcf5b38702cd9fd391cced9a7d54d325c/prysm/bayer.py#L359

    """
    The MIT License (MIT)

    Copyright (c) 2017 Brandon Dube

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
    rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
    THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
    """

    bayer = img.astype(np.float32)

    kernel_G_at_R_or_B = [
        [0, 0, -1, 0, 0], 
        [0, 0, 2, 0, 0], 
        [-1, 2, 4, 2, -1], 
        [0, 0, 2, 0, 0], 
        [0, 0, -1, 0, 0], 
    ]

    # R at green in R row, B column
    kernel_R_at_G_in_RB = [
        [0, 0, .5, 0, 0], 
        [0, -1, 0, -1, 0], 
        [-1, 4, 5, 4, -1], 
        [0, -1, 0, -1, 0], 
        [0, 0, .5, 0, 0], 
    ]

    kernel_R_at_G_in_BR = [
        [0, 0, -1, 0, 0], 
        [0, -1, 4, -1, 0], 
        [.5, 0, 5, 0, .5], 
        [0, -1, 4, -1, 0], 
        [0, 0, -1, 0, 0], 
    ]

    kernel_R_at_B_in_BB = [
        [0, 0, -3 / 2, 0, 0], 
        [0, 2, 0, 2, 0], 
        [-3 / 2, 0, 6, 0, -3 / 2], 
        [0, 2, 0, 2, 0], 
        [0, 0, -3 / 2, 0, 0], 
    ]

    kgreen = np.array(kernel_G_at_R_or_B) / 8.
    kgreensameColumn = np.array(kernel_R_at_G_in_RB) / 8.
    kgreensameRow = np.array(kernel_R_at_G_in_BR) / 8.
    kdiagonalRB = np.array(kernel_R_at_B_in_BB) / 8.

    # there is only one filter for G
    Gest = ndimage.convolve(img, kgreen)

    # there are only three unique convolutions remaining
    c1 = ndimage.convolve(img, kgreensameColumn)  # top is 0.5, left is -1
    c2 = ndimage.convolve(img, kgreensameRow)  # top is -1, left is 0.5
    c3 = ndimage.convolve(img, kdiagonalRB)  # top is -1.5

    red = np.empty_like(img)
    green = Gest
    blue = np.empty_like(img)

    top_left = (slice(0, None, 2), slice(0, None, 2))
    top_right = (slice(0, None, 2), slice(1, None, 2))
    bottom_left = (slice(1, None, 2), slice(0, None, 2))
    bottom_right = (slice(1, None, 2), slice(1, None, 2))

    green[top_right] = img[top_right]
    green[bottom_left] = img[bottom_left]

    # could below be np.choose?
    if pattern == 'rg':
        red[top_left] = img[top_left]
        red[top_right] = c1[top_right]
        red[bottom_left] = c2[bottom_left]
        red[bottom_right] = c3[bottom_right]

        blue[top_left] = c3[top_left]
        blue[top_right] = c2[top_right]
        blue[bottom_left] = c1[bottom_left]
        blue[bottom_right] = img[bottom_right]
    elif pattern == 'bg':
        blue[top_left] = img[top_left]
        blue[top_right] = c1[top_right]
        blue[bottom_left] = c2[bottom_left]
        blue[bottom_right] = c3[bottom_right]

        red[top_left] = c3[top_left]
        red[top_right] = c2[top_right]
        red[bottom_left] = c1[bottom_left]
        red[bottom_right] = img[bottom_right]
    else:
        raise KeyError(f"debayering - pattern '{pattern}' not found")

    return np.stack((red, green, blue), axis=2)

    return rgb


def debayer(img, algorithm='bilinear', pattern='gb'):
    """Debayering. Takes a 16bit 2D Numpy array, an algorithm and a debayering pattern string. Only the
    first band of a multi-band image will be used."""

    pattern = pattern.lower()
    algorithm = algorithm.lower()

    if len(img.shape) != 2:
        img = img[:, :, 0]  # if there is more than one band, use only the first

    if algorithm != 'mhc':
        return debayer_cv(img, algorithm, pattern)
    else:
        return debayer_mhc(img, pattern)

