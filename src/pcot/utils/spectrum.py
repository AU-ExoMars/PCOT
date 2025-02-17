"""
Extract spectra from ImageCube objects
"""
import dataclasses
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import numpy as np

from pcot.dq import BAD
from pcot.cameras.filters import Filter
from pcot.imagecube import ImageCube
from pcot.rois import ROI
from pcot.sources import SourceSet, SourcesObtainable
from pcot.utils.maths import pooled_sd
from pcot.utils.table import Table
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
        raise XFormException('DATA',"subimage has no pixels (size zero)")

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

        std = pooled_sd(a, np.ma.masked_array(data=chanUnc, mask=~mask))
    else:
        std = a.std()  # otherwise get the SD of the nominal values

    # return the mean, SD, and a zero value for the DQ (because there were good pixels)
    return mean, std, 0


@dataclass
class SpectrumValue:
    """The output of the get methods in Spectrum - a single value and the number of pixels from which
    it was obtained."""
    v: Value
    pixels: int  # the number of pixels from which the value was obtained

    def as_tuple(self):
        return dataclasses.astuple(self)


class Spectrum:
    """A single spectrum extracted from an ImageCube or ROI of an ImageCube. Only
    channels which have a single filter are used. Could conceivably have a single value
    if only a single valid channel is present, but if no valid channels are present
    an exception is raised. If all pixels in a channel are "bad" (DQ != 0) then the
    channel is ignored.

    If ignorePixSD is true, the SD of the result is the SD of the nominal values. Otherwise
    the SD is pooled (mean of the variances of the pixels plus the variance of the means
    of the pixels).
    """

    # the spectrum as a dictionary of filter:value  (typically reflectance)
    data: Dict[Filter, SpectrumValue]
    # list of filters ordered by channel number
    filters: List[Filter]
    # the sources from which the spectrum was extracted
    sources: SourceSet
    # the source image
    img: ImageCube
    # the ROI from which the spectrum was extracted (if any; None if the whole image)
    roi: Optional[ROI]
    # number channels in the spectrum - should be the same as img.channels
    # but later we might separate imagecubes from spectra.
    channels: int

    def __init__(self, img: ImageCube, roi: Optional[ROI] = None, ignorePixSD=False):
        self.img = img
        self.roi = roi
        self.data = {}
        self.channels = img.channels

        # first, generate a list of indices of channels with a single source which has a filter,
        # and a list of those filters.
        self.filters = [img.filter(x) for x in range(img.channels)]
        chans = [x for x in range(img.channels) if self.filters[x] is not None]
        if len(chans) == 0:
            raise XFormException("DATA", "no single-wavelength channels in image")

        # create a set of sources
        sources = set()
        for x in chans:
            sources |= img.sources.sourceSets[x].sourceSet
        self.sources = SourceSet(sources)

        subimg = img.subimage(roi=roi)

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
                pixct = subimg.pixelCount() - np.count_nonzero(dq.compressed())
                dq = np.bitwise_or.reduce(dq, axis=None) & BAD  # OR all the bad bits together
                self.data[f] = SpectrumValue(Value(mean, sd, dq), pixct)
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
                    # count. It's how you count non-zero values in a masked array. We only worry about
                    # the BAD pixels.
                    pixct = subimg.pixelCount() - np.count_nonzero(dq.compressed() & BAD)
                    dq = np.bitwise_or.reduce(dq, axis=None) & BAD  # OR all the bad bits together
                    self.data[f] = SpectrumValue(Value(mean, sd, dq), pixct)

    def get(self, cwlOrName) -> Optional[SpectrumValue]:
        """get the value and pixel count for a particular channel wavelength or filter name"""
        for f, v in self.data.items():
            if f.cwl == cwlOrName or f.name == cwlOrName:
                return v
        return None

    def getByChannel(self, channel) -> Optional[SpectrumValue]:
        """get the value for a particular channel number"""
        if channel < 0 or channel >= len(self.filters):
            return None
        f = self.filters[channel]
        return self.data[f] if f in self.data else None

    def __repr__(self):
        return "Spectrum: " + "; ".join([f"{f}:{v}" for f, v in self.data.items()])


class NameResolver:
    """It's possible that images will have different ROIs with the same name.
    In that case, we need to disambiguate them. This class does that.
    It contains a dictionary of (imagename, ROIname) -> name. Normally this will be the same
    as ROIname, but if the name appears multiple times, it will be "imagename:roiName".
    This is only used when images have ROIs - if they don't, this object isn't used.

    We also go to some lengths to make sure an ROI with a blank label is given a name.
    """
    @staticmethod
    def getLabel(rr: ROI) -> str:
        return rr.label if rr.label != "" else "no label"

    def __init__(self, d: Dict[str, ImageCube]):
        self.nameDict = {}
        self.countDict = {}
        # pass 1 - count each time a name appears for an ROI
        for name, img in d.items():
            for r in img.rois:
                label = NameResolver.getLabel(r)
                # increment the count for this label, setting it to 1
                # if it's not there
                self.countDict[label] = self.countDict.get(label, 0) + 1
        # pass 2 - create the name dictionary
        for name, img in d.items():
            for r in img.rois:
                label = NameResolver.getLabel(r)
                if self.countDict[label] > 1:
                    # this label appears in more than one image cube
                    # so we need to prefix the label with the name of the
                    # image cube
                    self.nameDict[(name, label)] = name + ":" + label
                else:
                    # this label appears only once
                    self.nameDict[(name, label)] = label

    def resolve(self, imgname, roi):
        return self.nameDict[(imgname, NameResolver.getLabel(roi))]


class SpectrumSet(dict, SourcesObtainable):
    """A set of Spectrum objects obtained from ImageCube objects. Each Spectrum is associated with an ImageCube
    or a subset of an ImageCube (ROI). Multiple ROIs of the same name within the same ImageCube will be combined
    into a single Spectrum.
    If there are multiple ROIs with the same name in different ImageCubes, the key will be the name of the
    ImageCube followed by a colon and the name of the ROI.

    This acts as a dict with the keys being the names of the ROIs and the values being the Spectrum objects.
    Multiple ROIs with the same name in the same ImageCube will be combined into a single Spectrum. Other methods are
    available to retrieve annotation colour data and a tabular representation.

    If ignorePixSD is true, the SD of the result is the SD of the nominal values. Otherwise
    the SD is pooled (mean of the variances of the pixels plus the variance of the means
    of the pixels).
    """

    # the problem here is that each spectrum can be associated with an imagecube, an ROI within an image, or a
    # set of ROIs within an image all with the same name.

    def __init__(self, images: Dict[str, ImageCube], ignorePixSD=False):
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
        SpectrumSet._coalesceROIs(images)
        # we need to create a name resolver to disambiguate ROIs with the same name
        # in different image cubes - we do this after the coalesce because we don't want
        # to disambiguate ROIs in the same image cube (they should be merged).
        resolver = NameResolver(images)

        # now we can create the spectra

        data = dict()
        cols = dict()
        sources = set()
        self.sources = SourceSet()  # empty source set initially

        for name, img in images.items():
            # first, generate a list of indices of channels with a single source which has a filter,
            # and a list of those filters.
            filters = [img.filter(x) for x in range(img.channels)]
            if len(filters) == 0:
                raise XFormException("DATA", "no single-wavelength channels in image")
            chans = [x for x in range(img.channels) if filters[x] is not None]
            # and use that to generate a set of sources
            for x in chans:
                sources |= img.sources.sourceSets[x].sourceSet
            self.sources = SourceSet(sources)

            # now we can create the spectrum for each ROI

            if len(filters) == 0:
                # here we are going to put a None field in the data dictionary
                # to indicate an error
                data[name] = None
                cols[name] = None
            elif len(img.rois) == 0:
                # there are no ROIs in this image cube. We'll create a single spectrum
                # for the whole image cube.
                data[name] = Spectrum(img, ignorePixSD=ignorePixSD)
                cols[name] = (0, 0, 0)  # no ROI, so no colour to be assigned
            else:
                # there are multiple ROIs in this image cube. We may need to prefix
                # the ROI name with the image cube name to disambiguate them if
                # there are multiple ROIs with the same name in different image cubes.
                for r in img.rois:
                    if r.bb() is None:
                        # this is an invalid ROI; we'll skip it.
                        continue
                    legend = resolver.resolve(name, r)
                    data[legend] = Spectrum(img, roi=r, ignorePixSD=ignorePixSD)
                    cols[legend] = r.colour

        # we now have a dictionary of spectra, keyed by name, and similarly
        # a dictionary of colours.
        # We initialise the dict with the data dictionary
        super().__init__(data)
        # and set the colours
        self.colours = cols

    def getColour(self, name: str) -> Tuple[float, float, float]:
        """return the colour associated with a spectrum"""
        return self.colours[name]

    def getSources(self) -> SourceSet:
        """return a set of all the sources in the spectra"""
        return self.sources

    def table(self):
        """Return a Table representation"""
        table = Table()
        for legend, spec in self.items():
            table.newRow(legend)
            table.add("name", legend)
            for i in range(spec.channels):
                f = spec.filters[i]
                w = int(f.cwl)
                p = spec.getByChannel(i)
                if p is None:
                    m = "NA"
                    s = "NA"
                    pct = 0
                else:
                    m = p.v.n
                    s = p.v.u
                    pct = p.pixels
                table.add("m{}".format(w), m)
                table.add("s{}".format(w), s)
                table.add("p{}".format(w), pct)
        return table

    @staticmethod
    def _coalesceROIs(images: Dict[str, ImageCube]):
        """coalesce ROIs with the same name in the same image cube. Modifies the
        dictionary which is passed in, replacing the image cubes with new ones
        if they contain multiple ROIs with the same name. The new image cubes
        contain those ROIs merged into single ROIs."""

        for name, img in images.items():
            rois = []  # list of ROIs in this cube
            replace = False  # should we replace the cube with a new one containing only the combined ROI?
            for r in img.rois:
                # look for another cube with the same name in the list we are building
                if r.label in [x.label for x in rois]:
                    # we have a duplicate. Combine them.
                    replace = True
                    # find the other ROI
                    other = [x for x in rois if x.label == r.label][0]
                    # combine them and copy the label from one (they'll be the same)
                    new = r + other
                    new.label = r.label
                    # remove the other ROI from the list
                    rois.remove(other)
                    # add the new one to the list
                    rois.append(new)
                else:
                    # no duplicate. Just add it to the list.
                    rois.append(r)
            if replace:
                # replace the cube with a new one containing only the combined ROI
                images[name] = img.shallowCopy()
                images[name].rois = rois

