import numpy as np

"""Various low-level image utilities"""


def imgsplit(img):
    """Does the same as cv.split, effectively, but is guaranteed to work on >3 channels. Who knows if CV will
    always do that."""
    return [np.reshape(x, img.shape[:2]) for x in np.dsplit(img, img.shape[-1])]


def imgmerge(img):
    """Trivial, but goes with imgsplit"""
    return np.dstack(img)
