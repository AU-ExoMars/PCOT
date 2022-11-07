from typing import Tuple, List, Optional

import numpy as np
from PySide2.QtCore import QPointF
from PySide2.QtGui import QImage, QLinearGradient, QGradient

from pcot.utils.colour import rgb2qcol


class Gradient:
    # the actual gradient data consists of a number of points from 0..1, each with an RGB
    # value. Each component in that value is 0-1.
    data: List[Tuple[float, Tuple[float, float, float]]]
    # is the current cached QImage vertical (if it exists)?
    vertical: bool
    # currently cached QImage if there is one
    image: Optional[QImage]

    def __init__(self, d):
        """Set up the gradient with the given values"""
        self.image = None
        self.vertical = False  # not that it matters...
        self.setData(d)

    def setData(self, d):
        self.data = d

    def serialise(self):
        return self.data

    def deserialise(self, d):
        self.data = d

    def apply(self, img, mask):
        """Given a 2D 1-channel numpy array, a mask (in which the True items are to be processed, so not the standard
        masked array convention), return an RGB image which is that monochrome image converted into the gradient.
        Parts of the image which are masked remain monochrome, but with the same values across all 3 channels.

        Inputs:
            - img: a greyscale image
            - mask: which parts should be processed
        Output:
            - an RGB image
        """
        masked = np.ma.masked_array(img, mask=~mask)
        if len(img.shape) != 2:
            raise Exception("error in gradient: not a monochrome image")

        # construct 3 channel copy of image to write into
        cp = np.dstack((img, img, img))
        # turn gradient into lookup tables for each channel
        xs = np.array([x for x, (r, g, b) in self.data])
        rs = np.array([r for x, (r, g, b) in self.data])
        gs = np.array([g for x, (r, g, b) in self.data])
        bs = np.array([b for x, (r, g, b) in self.data])
        # build the r,g,b channels with interpolation into the lookup
        rs = np.interp(masked, xs, rs)
        gs = np.interp(masked, xs, gs)
        bs = np.interp(masked, xs, bs)
        # and stack them into a single image. To do this, though, we
        # need the full 3 channel mask.
        h, w = mask.shape
        # flatten and repeat each element thrice
        mask3 = np.repeat(np.ravel(mask), 3)
        # put into a h,w,3 array
        mask3 = np.reshape(mask3, (h, w, 3))
        # write to the 3 channel copy using that mask
        np.putmask(cp, mask3, np.dstack((rs, gs, bs)).astype(np.float32))
        return cp

    def getGradient(self, vertical=False):
        """Create a QLinearGradient"""
        if vertical:
            grad = QLinearGradient(QPointF(0, 1), QPointF(0, 0))
        else:
            grad = QLinearGradient(QPointF(0, 0), QPointF(1, 0))
        grad.setCoordinateMode(QGradient.ObjectMode)
        dat = self.data.copy()
        if dat[0][0] != 0.0:
            dat.insert(0, (0, dat[0][1]))
        if dat[-1][0] != 1.0:
            dat.append((1, dat[-1][1]))
        for x, (r, g, b) in dat:
            grad.setColorAt(x, rgb2qcol((r, g, b)))
        return grad
