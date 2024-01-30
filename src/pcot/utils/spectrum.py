"""
Extract spectra from ImageCube objects
"""
from abc import ABC
from typing import Dict, Optional, Tuple, List

import numpy as np

from pcot.dq import BAD
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.rois import ROI
from pcot.sources import SourceSet, SourcesObtainable
from pcot.value import Value
from pcot.xform import XFormException


def getMeanValue(chanImg, chanUnc, chanDQ, mask, ignorePixSD=False):
    """find the mean/sd of all the masked values in a single channel for a subimage
    (ie. part of an image cut out by an ROI). If ignorePixSD is true, the SD of the
    result is the SD of the nominal values. Otherwise the SD is pooled (mean of the variances
    of the pixels plus the variance of the means of the pixels).

    If all the pixels are masked out, return None for both mean and SD, and a third value (normally zero)
    which is the OR of all the bad bits in the DQ.
    """

    # if the size is bad, throw an exception
    if mask.size == 0:
        raise XFormException("subimage has no pixels (size zero)")

    # note that "mask" is a positive mask - values are True if we are using them.
    if mask is None:
        mask = np.full(chanImg.shape, True)  # no bits masked out
    else:
        mask = np.copy(mask)  # need a copy or we'll change the mask in the subimage.
    # we also have to mask out the bad bits. This will give us a mask which is True
    # for the bits we want to hide.
    badmask = (chanDQ & BAD).astype(bool)
    mask &= ~badmask  # REMOVE those pixels

    # if ALL the values are bad, return None for both mean and SD, and a third
    # value which is all the bad pixels' bits ORed together.
    if not np.any(mask):
        badBits = np.bitwise_or.reduce(chanDQ, axis=None) & BAD  # OR all the bad bits together
        return None, None, badBits

    # otherwise we can proceed
    a = np.ma.masked_array(data=chanImg, mask=~mask)
    mean = a.mean()  # get the mean of the nominal values

    if not ignorePixSD:
        # we're going to try to take account of the uncertainties of each pixel:
        # "Thus the variance of the pooled set is the mean of the variances plus the variance of the means."
        # by https://arxiv.org/ftp/arxiv/papers/1007/1007.1012.pdf
        # So we'll calculate the variance of the means added to the mean of the variances.
        # And then we'll need to root that variance to get back to SD.
        # There is a similar calculation called pooled_sd() in builtins!

        std = np.sqrt(a.var() + np.mean(np.ma.masked_array(data=chanUnc, mask=~mask) ** 2))
    else:
        std = a.std()  # otherwise get the SD of the nominal values

    # return the mean, SD, and a zero value for the DQ (because there were good pixels)
    return mean, std, 0


class Spectrum:
    """A single spectrum extracted from an ImageCube or ROI of an ImageCube. Only
    channels which have a single filter are used. Could conceivably have a single value
    if only a single valid channel is present, but if no valid channels are present
    an exception is raised. If all pixels in a channel are "bad" (DQ != 0) then the
    channel is ignored."""

    # the spectrum as a dictionary of filter:value  (typically reflectance)
    data: Dict[Filter, Value]
    # list of filters ordered by channel number
    filters: List[Filter]
    # the sources from which the spectrum was extracted
    sources: SourceSet
    # the source image
    cube: ImageCube
    # the ROI from which the spectrum was extracted (if any; None if the whole image)
    roi: Optional[ROI]
    # the number of pixels each band in the ROI (or image if none). Usually they're all the same,
    # but if the ROI has some bad pixels in one channel they might not be.
    pixels: Dict[Filter, int]
    # number channels in the spectrum - should be the same as cube.channels
    # but later we might separate imagecubes from spectra.
    channels: int

    def __init__(self, cube: ImageCube, roi: Optional[ROI] = None, ignorePixSD=False):
        self.cube = cube
        self.roi = roi
        self.data = {}
        self.pixels = {}
        self.channels = cube.channels

        # first, generate a list of indices of channels with a single source which has a filter,
        # and a list of those filters.
        self.filters = [cube.filter(x) for x in range(cube.channels)]
        chans = [x for x in range(cube.channels) if self.filters[x] is not None]
        if len(self.filters) == 0:
            raise XFormException("DATA", "no single-wavelength channels in image")

        # create a set of sources
        sources = set()
        for x in chans:
            sources |= cube.sources.sourceSets[x].sourceSet
        self.sources = SourceSet(sources)

        subimg = cube.subimage(roi=roi)

        # todo refactor this - there's a lot of duplication
        if len(chans) == 1:
            # single channel images are stored as 2D arrays.
            mean, sd, allBitsDQ = getMeanValue(subimg.img[:, :], subimg.uncertainty[:, :], subimg.dq[:, :],
                                               subimg.mask,
                                               ignorePixSD=ignorePixSD)
            # we don't add "bad" data
            if allBitsDQ != 0:
                # the channel number will be chans[0] (there is only one)
                # the filter will be filters[chans[0]]
                f = self.filters[chans[0]]
                # subtract bad pixels from the pixel count
                dq = subimg.maskedDQ()
                # this will compress the array (give a 1D array of all the unmasked pixels) and then
                # count. It's how you count non-zero values in a masked array.
                self.pixels[f] = subimg.pixelCount() - np.count_nonzero(dq.compressed())
                dq = np.bitwise_or.reduce(dq, axis=None) & BAD  # OR all the bad bits together
                self.data[f] = Value(mean, sd, dq)
        else:
            for cc in chans:
                mean, sd, allBitsDQ = getMeanValue(subimg.img[:, :, cc], subimg.uncertainty[:, :, cc],
                                                   subimg.dq[:, :, cc],
                                                   subimg.mask,
                                                   ignorePixSD=ignorePixSD)
                # we don't add "bad" data
                if allBitsDQ == 0:
                    # the channel number will be cc
                    # the filter will be filters[cc]
                    f = self.filters[cc]
                    # subtract bad pixels from the pixel count
                    dq = subimg.maskedDQ()[:, :, cc]  # get the masked DQ, extract one channel
                    # this will compress the array (give a 1D array of all the unmasked pixels) and then
                    # count. It's how you count non-zero values in a masked array.
                    self.pixels[f] = subimg.pixelCount() - np.count_nonzero(dq.compressed())
                    dq = np.bitwise_or.reduce(dq, axis=None) & BAD  # OR all the bad bits together
                    self.data[f] = Value(mean, sd, dq)

    def getByFilter(self, cwlOrName) -> Optional[Tuple[Value, int]]:
        """get the value and pixel count for a particular channel wavelength or filter name"""
        for f, v in self.data.items():
            if f.cwl == cwlOrName or f.name == cwlOrName:
                return v, self.pixels[f]
        return None

    def getByChannel(self, channel):
        """get the value for a particular channel number"""
        if channel < 0 or channel >= len(self.filters):
            return None
        f = self.filters[channel]
        return (self.data[f], self.pixels[f]) if f in self.data else (None, 0)

    def __repr__(self):
        return "Spectrum: " + "; ".join([f"{f}:{v}" for f, v in self.data.items()])


class SpectrumSet(SourcesObtainable):
    """A set of Spectrum objects obtained from ImageCube objects. Each Spectrum is associated with an ImageCube
    or a subset of an ImageCube (ROI). Multiple ROIs of the same name within the same ImageCube will be combined
    into a single Spectrum."""

    # the problem here is that each spectrum can be associated with an imagecube, an ROI within an image, or a
    # set of ROIs within an image all with the same name.

    def __init__(self, images: Dict[str, ImageCube]):
        """create a set of spectra from a dictionary of ImageCube objects and the ROIs they contain.
        The keys are the names of the ImageCubes and the values are the ImageCube objects. The names
        are used to to disambiguate regions of interest (ROIs) within the image cubes.

        A spectrum is created for every ROI in every image cube. If there are multiple ROIs with the same
        name in the same image cube, they are combined into a single spectrum. If there are multiple ROIs
        with the same name in different image cubes, they are kept separate and the name associated with the
        spectrum is the image cube name followed by a colon and the ROI name.
        """

        # First step - we need to combine ROIs with the same name in the same image cube. We iterate over
        # the image cubes. If a cube contains multiple ROIs with the same name, we combine them into a single
        # ROI and delete the others, replacing the image cube with a new one containing only the combined ROI (as
        # a shallow copy).

        for name, cube in images.items():
            rois = []           # list of ROIs in this cube
            replace = False     # should we replace the cube with a new one containing only the combined ROI?
            for r in cube.rois:
                # look for another cube with the same name in the list we are building
                if r.label in [x.label for x in rois]:
                    # we have a duplicate. Combine them.
                    replace = True
                    # find the other ROI
                    other = [x for x in rois if x.label == r.label][0]
                    # combine them
                    new = r+other
                    # remove the other ROI from the list
                    rois.remove(other)
                    # add the new one to the list
                    rois.append(new)
                else:
                    # no duplicate. Just add it to the list.
                    rois.append(r)
            if replace:
                # replace the cube with a new one containing only the combined ROI
                images[name] = cube.shallowCopy()
                images[name].rois = rois

        # now we can create the spectra

        data = dict()
        cols = dict()
        sources = set()

        for name, cube in images.items():
            # first, generate a list of indices of channels with a single source which has a filter,
            # and a list of those filters.
            filters = [cube.filter(x) for x in range(cube.channels)]
            if len(filters) == 0:
                raise XFormException("DATA", "no single-wavelength channels in image")
            chans = [x for x in range(cube.channels) if filters[x] is not None]
            # and use that to generate a list of sources
            for x in chans:
                sources |= cube.sources.sourceSets[x].sourceSet
            # now we can create the spectrum for each ROI

            # todo

    def getSources(self) -> SourceSet:
        pass

