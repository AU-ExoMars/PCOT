from typing import Tuple, List, Optional

import numpy as np
from PySide2.QtGui import QImage


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

    def getImage(self, vertical=False):
        """This returns a cached QImage we can use for rendering a legend."""
        if self.image is None or self.vertical != vertical:
            # need to rebuild the image; either it's not there or the orientation is wrong
            self.vertical = vertical
            # we'll construct the image horizontally and transpose if we want vertical.
            width = 64
            height = 8
            # turn gradient into lookup tables for each channel
            xs = np.array([x for x, (r, g, b) in self.data])
            rs = np.array([r for x, (r, g, b) in self.data])
            gs = np.array([g for x, (r, g, b) in self.data])
            bs = np.array([b for x, (r, g, b) in self.data])
            # we're looking at n=width values from 0..1
            vals = np.linspace(0, 1, num=width)
            # and build those values for each channel
            rs = np.interp(vals, xs, rs)
            gs = np.interp(vals, xs, gs)
            bs = np.interp(vals, xs, bs)
            # this is a rubbish way to do it
            img = np.zeros((height, width, 3), dtype=np.float)
            for i in range(width):
                img[:, i] = (rs[i], gs[i], bs[i])
            if vertical:
                img = img.transpose().copy()  # copy to make it column-contiguous memory for QImage
                width, height = height, width
            self.image = QImage(img.data, width, height, width*3, QImage.Format_RGB888)
            self.membuffer = img    # to avoid the annoying early free (see other uses of QImage)

        return self.image

    def clearImage(self):
        """Clear cached image"""
        self.image = None
