"""Classes to encapsulate an image data cube which can be any number of channels
and also incorporates region-of-interest data.  Conversions to and from float are
done in many operations. Avoiding floats saves memory and speeds things up,
but we could change things later.
"""

import logging
import math
import numbers
from typing import List, Optional, Tuple, Sequence, Union, Callable

import cv2 as cv
import numpy as np
from PySide2.QtGui import QPainter

from pcot.documentsettings import DocumentSettings
from pcot.rois import ROI, ROIPainted, ROIBoundsException
from pcot.sources import MultiBandSource, SourcesObtainable
from pcot.utils import annotations
from pcot.utils.annotations import TestAnnotation, annotFont
from pcot.utils.geom import Rect

logger = logging.getLogger(__name__)

class SubImageCubeROI:
    """This is a class representing the parts of an imagecube which are covered by ROIs or an ROI.
    It consists of
    * the image cropped to the bounding box of the ROIs; this is a view into the original image.
    * the data for the BB (x,y,w,h)
    * a boolean mask the same size as the BB, True for pixels contained in the ROIs and which
      should be manipulated.
    """

    def __init__(self, img, imgToUse=None, roi=None, clip=True):
        """
        img - the image in which we are finding the subimage
        imgToUse - used if we are actually getting the ROIs from another image
        roi - used if we are getting the subimage for an arbitrary ROI
        clip - used if we should clip the ROI to the image; alternative is ROIBoundsException

        Note that ROIBoundsException can still occur if the ROI is entirely outside the image!
        """
        rois = img.rois if imgToUse is None else imgToUse.rois
        self.channels = img.channels

        if roi is not None:
            # we're not using the image ROIs, we're using one passed in. Make a list of it.
            rois = [roi]

        genFullImage = True  # true if there is no valid ROI
        if len(rois) > 0:
            # construct a temporary ROI union of all the ROIs on this image
            roi = ROI.roiUnion(rois)
            if roi is not None:  # if the ROI union is OK
                genFullImage = False
                self.bb = roi.bb()  # the bounding box within the image
                self.mask = roi.mask()  # the ROI's mask, same size as the BB
                imgBB = (0, 0, img.w, img.h)
                # get intersection of ROI BB and image BB
                intersect = self.bb.intersection(imgBB)
                if intersect is None:
                    # no intersection, ROI outside image
                    raise ROIBoundsException()
                if intersect != self.bb:
                    # intersection is not equal to ROI BB, we must clip
                    if clip:
                        roi = roi.clipToImage(img)
                        self.bb = roi.bb()
                        self.mask = roi.mask()
                    else:
                        raise ROIBoundsException()

                x, y, w, h = self.bb  # this works even though self.bb is Rect
                self.img = img.img[y:y + h, x:x + w]

                if self.img.shape[:2] != self.mask.shape:
                    raise Exception("Internal error: shape still incorrect after clip")

        if genFullImage:
            # here we just make a copy of the image
            self.img = np.copy(img.img)  # make a copy to avoid descendant nodes changing their input nodes' outputs
            self.bb = Rect(0, 0, img.w, img.h)  # whole image
            self.mask = np.full((img.h, img.w), True)  # full mask

    ## the main mask is just a single channel - this will generate a mask
    # of the same number of channels, so an x,y image will make an x,y mask
    # and an x,y,n image will make an x,y,n mask.
    def fullmask(self):
        if len(self.img.shape) == 2:
            return self.mask  # the existing mask is fine
        else:
            h, w, chans = self.img.shape
            # flatten and repeat each element for each channel
            x = np.repeat(np.ravel(self.mask), chans)
            # put into a h,w,chans array
            return np.reshape(x, (h, w, chans))

    # get the masked image
    def masked(self):
        return np.ma.masked_array(self.img, mask=~self.fullmask())

    ## use this ROI to crop the image in img2. Doesn't do masking, though.
    # Copies the sources list from that image.
    def cropother(self, img2):
        x, y, w, h = self.bb
        return ImageCube(img2.img[y:y + h, x:x + w], img2.mapping, img2.sources)

    ## Compare two subimages - just their regions of interest, not the actual image data
    # Will also work if the images are different depths.
    def sameROI(self, other):
        return self.bb == other.bb and self.mask == other.mask

    ## pixel count
    def pixelCount(self):
        return self.mask.sum()


## A mapping from a multichannel image into RGB. All nodes have one of these, although some may have more and some
# might not even use this one. That's because most (or at least many) nodes generate a single image and show it
# in their tab. Ideally, I should create one of these in just those nodes but I'm lazy.

class ChannelMapping:
    def __init__(self, red=-1, green=-1, blue=-1):
        # the mapping itself : channels to use in the source image for red,green,blue
        self.red = red
        self.green = green
        self.blue = blue

    def set(self, r, g, b):
        self.red = r
        self.green = g
        self.blue = b

    def generateMappingFromDefaultOrGuess(self, img):
        """Generate a new RGB mapping. If defaultMapping is present in the image, we use that. Otherwise, we try to
        guess one from the bands in the image by picking the single-channel band with a wavelength closest to the
        R,G,B wavelengths. If there are more than one (e.g. PanCam's left camera has two 440 filters) we use the
        widest. If no candidates can be found we just use any band."""
        if img.defaultMapping is not None:
            self.set(img.defaultMapping.red, img.defaultMapping.green, img.defaultMapping.blue)
        else:
            # get indices of closest and widest band to wavelength,
            # or -1 if one can't be found

            r = img.wavelengthBand(640)
            g = img.wavelengthBand(540)
            b = img.wavelengthBand(440)

            # if any of those fail, look for bands whose names filter names are 'R', 'G' or 'B'. These
            # still also return -1 if not found.
            if r < 0:
                r = img.namedFilterBand('R')
            if g < 0:
                g = img.namedFilterBand('G')
            if b < 0:
                b = img.namedFilterBand('B')

            # generate a list of all the channels, with the ones found NOT in it.
            lst = [x for x in range(img.channels) if x not in (r, g, b)]
            # and finally replace r,g,b with things from the above list if they are -ve, but
            # first appending the entire range to lst just in case it is empty.
            lst = lst + [min(x, img.channels - 1) for x in (0, 1, 2)]

            # and extract, popping in reverse order to ensure the "default" mapping
            # is 0,1,2 when there is no wavelength data at all.
            b = b if b >= 0 else lst.pop()
            g = g if g >= 0 else lst.pop()
            r = r if r >= 0 else lst.pop()
            # FINALLY, finally. Make sure those bands are in descending wavelength order. This
            # deals with cases where all the wavelengths (say) are very high.
            lst = [(x, img.wavelength(x)) for x in (r, g, b)]
            lst.sort(key=lambda v: -v[1])
            self.red, self.green, self.blue = [x[0] for x in lst]

    # generate a mapping from a new image if required - or keep using the old mapping
    # if we can. Return self, for fluent.
    def ensureValid(self, img):
        # make sure there is a mapping, and that it's in range. If not, regenerate.
        if self.red < 0 or self.red >= img.channels or self.green >= img.channels or self.blue >= img.channels:
            # if there's a default mapping in the image we will use that. If not, then we'll guess!
            # This can also be used to generate a default mapping itself.
            self.generateMappingFromDefaultOrGuess(img)
        return self

    def serialise(self):
        return [self.red, self.green, self.blue]

    @staticmethod
    def deserialise(lst):
        m = ChannelMapping()
        m.red, m.green, m.blue = lst
        return m

    def copy(self):
        m = ChannelMapping(self.red, self.green, self.blue)
        return m

    def __str__(self):
        return "ChannelMapping-{} r{} g{} b{}".format(id(self), self.red, self.green, self.blue)


class ImageCube(SourcesObtainable):
    """
    an image - just a numpy array (the image) and a list of ROI objects. The array
    has shape either (h,w) (for a single channel) or (h,w,n) for multiple channels.
    Images are 32-bit float.
    An RGB mapping can be provided, saying how the image should be represented in RGB (via the rgb() method)
    There is also a MultiBandSource describing the source sets associated with each channel.
    """
    ## @var img
    # the numpy array containing the image data
    img: np.ndarray

    ## @var rois
    # the regions of interest - these are also annotations! They are in a separate list
    # so they can be passed through or removed separately.
    rois: List[ROI]

    ## list of annotations - things that can be drawn on an image.
    annotations: List[annotations.Annotation]

    ## @var shape
    # the shape of the image array (i.e. the .shape field) - a single channel image will be a 2D array,
    # a multichannel image will be 3D.
    shape: Tuple

    ## @var channels
    # how many channels the image has.
    channels: int

    ## @var sources
    # a list of sets of sources - one set for each channel - describing where this data came from
    sources: MultiBandSource

    ## @var mapping
    # The RGB mapping to convert this image into RGB. May be None
    mapping: Optional[ChannelMapping]

    # create image from numpy array
    def __init__(self, img: np.ndarray, rgbMapping: ChannelMapping = None, sources: MultiBandSource = None,
                 defaultMapping: ChannelMapping = None):

        if img is None:
            raise Exception("trying to initialise image from None")
        self.img = img  # the image numpy array
        # first, check the dtype is valid
        if self.img.dtype != np.float32:
            raise Exception("Images must be 32-bit floating point")
        self.rois = []  # no ROI
        self.annotations = []  # and no annotations
        self.shape = img.shape
        # set the image type
        if len(img.shape) == 2:
            # 2D image
            self.channels = 1
        else:
            self.channels = img.shape[2]
        self.w = img.shape[1]
        self.h = img.shape[0]
        # an image may have a list of source data attached to it indexed by channel. Or if none is
        # provided, an empty one.
        self.sources = sources if sources else MultiBandSource.createEmptySourceSets(self.channels)
        self.defaultMapping = None

        # get the mapping sorted, which may be None (in which case rgb() might not work).
        # Has to be done after the sources are set.
        if rgbMapping is None:
            rgbMapping = ChannelMapping().ensureValid(self)
        self.setMapping(rgbMapping)

    #        if len(sources)==0:
    #            raise Exception("No source")

    # Set the RGB mapping for this image, and create default channel mappings if necessary.
    def setMapping(self, mapping: ChannelMapping):
        #        print("{} changing mapping to {}".format(self, self.mapping))
        self.mapping = mapping
        if mapping is not None:
            mapping.ensureValid(self)

    ## class method for loading an image (using cv's imread)
    # Always builds an RGB image. Sources must be provided.
    @classmethod
    def load(cls, fname, mapping, sources):
        fname = str(fname)  # fname could potentially be some kind of Path object.
        logger.info(f"ImageCube load: {fname}")
        # imread with this argument will load any depth, any
        # number of channels
        img = cv.imread(fname, -1)
        if img is None:
            raise Exception(f'Cannot read file {fname}')
        if len(img.shape) == 2:  # expand to RGB. Annoyingly we cut it down later sometimes.
            img = cv.merge((img, img, img))
        # get the scaling factor
        if img.dtype == np.uint8:
            scale = 255.0
        elif img.dtype == np.uint16:
            scale = 65535.0
        else:
            scale = 1.0
        # convert from BGR to RGB (OpenCV is weird)
        img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        # convert to floats (32 bit)
        img = img.astype(np.float32)
        # scale to 0..1 
        img /= scale
        # and construct the image
        return cls(img, mapping, sources)

    def rgb(self, showROIs: bool = False, mapping: Optional[ChannelMapping] = None) -> np.ndarray:
        """get a numpy image (not another ImageCube) we can display on an RGB surface - see
        rgbImage if you want an imagecube. If there is more than one channel we need to have
        an RGB mapping in the image. If showROIs is true, we create an image with the ROIs
        on it. We can specify a different mapping than that of the image."""
        if self.channels == 1:
            # single channel images are a special case, rather than
            # [chans,w,h] they are just [w,h]
            return cv.merge([self.img, self.img, self.img])
        else:
            if mapping is None:
                mapping = self.mapping
            if mapping is None:
                raise Exception("trying to get rgb of an imagecube with no mapping")
            red = self.img[:, :, mapping.red]
            green = self.img[:, :, mapping.green]
            blue = self.img[:, :, mapping.blue]
        img = cv.merge([red, green, blue])
        if showROIs:
            self.drawROIs(img)
        return img

    def rgbImage(self, mapping: Optional[ChannelMapping] = None) -> 'ImageCube':
        """as rgb, but wraps in an ImageCube. Also works out the sources, which should be for
        the channels in the result. A different mapping from the image mapping can be specified."""

        # The RGB mapping here should be just [0,1,2], since this output is the RGB representation.
        return ImageCube(self.rgb(mapping=mapping), ChannelMapping(0, 1, 2), self.rgbSources(mapping))

    def rgbSources(self, mapping=None):
        """Return the sources for the RGB mapped channels - used in rgbImage(), but handy in association
        with rgb() if you don't want a full ImageCube but need sources."""
        if mapping is None:
            mapping = self.mapping
        if mapping is None:
            raise Exception("trying to get rgb of an imagecube with no mapping")
        sourcesR = self.sources.sourceSets[mapping.red]
        sourcesG = self.sources.sourceSets[mapping.green]
        sourcesB = self.sources.sourceSets[mapping.blue]
        return MultiBandSource([sourcesR, sourcesG, sourcesB])

    def rgbWrite(self, filename):
        """save RGB representation"""
        img = self.rgb()
        # convert to 8-bit integer from 32-bit float
        img8 = (img * 256).clip(max=255).astype(np.ubyte)
        # and change endianness
        img8 = cv.cvtColor(img8, cv.COLOR_RGB2BGR)
        cv.imwrite(filename, img8)

    def drawROIs(self, rgb: np.ndarray = None, onlyROI: Union[ROI, Sequence] = None) -> np.ndarray:
        """Return an RGB representation of this image with any ROIs drawn on it - an image may be provided.
        onlyROI indicates that only one ROI should be drawn. We can also pass a Sequence of ROIs in (added
        later to support multidot ROIs)."""
        if rgb is None:
            rgb = self.rgb()

        if onlyROI is None:
            for r in self.rois:
                r.draw(rgb)
        elif isinstance(onlyROI, Sequence):
            for r in onlyROI:
                r.draw(rgb)
        else:
            onlyROI.draw(rgb)
        return rgb

    ## extract the "subimage" - the image cropped to regions of interest,
    # with a mask for those ROIs. Note that you can also supply an image,
    # in which case you get this image cropped to the other image's ROIs!
    # You can also limit to a single ROI or use all of them (the default)
    def subimage(self, imgToUse=None, roi=None):
        return SubImageCubeROI(self, imgToUse, roi)

    def __str__(self):
        s = "<Image-{} {}x{} array:{} channels:{}, {} bytes, ".format(id(self), self.w, self.h,
                                                                      str(self.img.shape), self.channels,
                                                                      self.img.nbytes)
        # caption type 0 is filter positions only
        xx = self.sources.brief()

        s += "src: [{}]".format(xx)
        xx = [r.bb() for r in self.rois]
        xx = [x for x in xx if x]  # filter out None
        xx = [", ROI {},{},{}x{}".format(x, y, w, h) for x, y, w, h in xx if xx]
        s += "/".join(xx) + ">"
        return s

    ## the descriptor is a string which can vary depending on main window settings.
    # If channel assignments are provided (e.g. [0,1,2]) select those channels and
    # show the descriptors for only those. Used in canvas. Not sure about it: on the one
    # hand we lose information (if we're viewing 3 channels from 11) but on the other hand
    # 11 channels is far too many to show in the descriptor at the bottom of the canvas!

    def getDesc(self, graph):
        if graph.doc.settings.captionType == DocumentSettings.CAP_NONE:
            return ""
        out = [s.brief(graph.doc.settings.captionType) for s in self.sources.sourceSets]
        # if there are channel assignments, show only the assigned channels. Not sure about this.
        if self.mapping is not None:
            out = [out[x] for x in [self.mapping.red, self.mapping.green, self.mapping.blue]]
        desc = " ".join(["[" + s + "]" for s in out])
        return desc

    def copy(self, keepMapping=False):
        """copy an image. If keepMapping is false, the image mapping will also be a copy. If true, the mapping
        is a reference to the same mapping as in the original image. If you notice
        # that you're changing the RGB mappings in a canvas and the image isn't changing,
        # it might be because of this."""
        if self.mapping is None or keepMapping:
            m = self.mapping
        else:
            m = self.mapping.copy()

        srcs = self.sources.copy()

        # we should be able to copy the default mapping reference OK, it won't change.
        i = ImageCube(self.img.copy(), m, srcs, defaultMapping=self.defaultMapping)
        i.rois = self.rois.copy()
        return i

    def hasROI(self):
        return len(self.rois) > 0

    def modifyWithSub(self, subimage: SubImageCubeROI, newimg: np.ndarray,
                      sources=None, keepMapping=False) -> 'ImageCube':
        """return a copy of the image, with the given image spliced in at the
        subimage's coordinates and masked according to the subimage.
        keppMapping will ensure that the new image has the same mapping as the old."""

        i = self.copy(keepMapping)
        x, y, w, h = subimage.bb
        i.img[y:y + h, x:x + w][subimage.mask] = newimg[subimage.mask]
        # can replace sources if required
        if sources is not None:
            i.sources = sources
        return i

    def getChannelImageByFilter(self, filterNameOrCWL):
        """Given a filter name, position or CWL, get a list of all channels which use it. Then build an image
        out of those channels. Usually this returns a single channel image, but it could very easily not."""
        # get list of matching channel indices (often only one)
        lstOfChannels = self.sources.search(filterNameOrCWL=filterNameOrCWL)
        if len(lstOfChannels) == 0:
            return None  # no matches found
        chans = []
        sources = []
        # now create a list of source sets and a list of single channel images
        for i in lstOfChannels:
            sources.append(self.sources.sourceSets[i])
            chans.append(self.img[:, :, i])
        if len(lstOfChannels) == 1:
            # single channel case
            img = chans[0]
        else:
            # else create a new multichannel image
            img = np.stack(chans, axis=-1)
        # and a new imagecube
        return ImageCube(img, sources=MultiBandSource(sources))

    ## annoyingly similar to the two methods above, this is used to get a channel _index_.
    def getChannelIdx(self, nameOrCwl):
        for i in range(len(self.sources.sourceSets)):  # iterate so we have the index
            x = self.sources[i]
            if len(x) == 1:
                # there must be only one source in the set; get it.
                item = next(iter(x))
                # match either the filter name or position, case-dependent
                iname = item.getFilterName()
                ipos = item.getFilterPos()
                if iname == nameOrCwl or ipos == nameOrCwl:
                    return i
                if isinstance(nameOrCwl, numbers.Number):
                    f = item.getFilter()
                    if f is not None and math.isclose(nameOrCwl, f.cwl):
                        return i
        return None

    ## crop an image down to its regions of interest, creating a new painted ROI.
    def cropROI(self):
        subimg = self.subimage()
        img = ImageCube(subimg.img, rgbMapping=self.mapping, defaultMapping=self.defaultMapping, sources=self.sources)
        img.rois = [ROIPainted(subimg.mask, "crop")]
        return img

    ## perform a simple function on an image's ROI or the whole image if there is no ROI
    def func(self, fn):
        img = self.subimage()
        mask = img.fullmask()  # get mask with same shape as below image
        img = img.img  # get imagecube bounded by ROIs as np array
        masked = np.ma.masked_array(img, mask=~mask)
        return fn(masked)

    ## attach an RGB mapping. If no arguments, it's the default mapping. If arguments are
    # provided, they are filter names or wavelengths and ALL THREE must be present. OR it's a list of actual
    # RGB indices. So the possible calls are:  (), (name,name,name), (cwl,cwl,cwl) or ([idx,idx,idx])
    def setRGBMapping(self, r=None, g=None, b=None):
        if isinstance(r, list) or isinstance(r, tuple):
            self.mapping = ChannelMapping(*r)
        elif r is not None or b is not None or g is not None:
            if r is None or b is None or g is None:
                raise Exception("All three RGB channel IDs or none must be provided in setRGBMapping")

            idxs = self.sources.search(filterNameOrCWL=r)
            if len(idxs) == 0:
                raise Exception("cannot find channel {}".format(r))
            ridx = idxs[0]

            idxs = self.sources.search(filterNameOrCWL=g)
            if len(idxs) == 0:
                raise Exception("cannot find channel {}".format(g))
            gidx = idxs[0]

            idxs = self.sources.search(filterNameOrCWL=b)
            if len(idxs) == 0:
                raise Exception("cannot find channel {}".format(b))
            bidx = idxs[0]

            self.mapping = ChannelMapping(ridx, gidx, bidx)
        else:
            self.mapping = ChannelMapping()  # default

        self.mapping.ensureValid(self)

    def getSources(self):
        return self.sources.getSources()

    def serialise(self):
        """Used to serialise imagecube Datums for serialisation of inputs when saving to a file"""
        return {
            'data': self.img,
            'mapping': self.mapping.serialise(),
            'defmapping': self.defaultMapping.serialise() if self.defaultMapping else None,
            'sources': self.sources.serialise()
        }

    @classmethod
    def deserialise(cls, d, document):
        """Inverse of serialise(), requires a document to get the inputs"""
        data = d['data']  # should already have been converted into an ndarray
        mapping = ChannelMapping.deserialise(d['mapping'])
        defmapping = None if d['defmapping'] is None else ChannelMapping.deserialise(d['defmapping'])
        sources = MultiBandSource.deserialise(d['sources'], document)
        return cls(data, rgbMapping=mapping, sources=sources, defaultMapping=defmapping)

    def wavelengthAndFWHM(self, channelNumber):
        """get cwl and mean fwhm for a channel if all sources are of the same wavelength, else -1. Compare with
        wavelength() below."""
        # get the SourceSet
        sources = self.sources.sourceSets[channelNumber]
        # all sources in this channel should have a filter
        sources = [s for s in sources.sourceSet if s.getFilter()]
        # all the sources in this channel should have the same cwl
        wavelengthsAndFWHMs = set([(s.getFilter().cwl, s.getFilter().fwhm) for s in sources])
        # extract the wavelengths and make sure there's only one
        wavelengths = set([t[0] for t in wavelengthsAndFWHMs])
        if len(wavelengths) != 1:
            return -1, -1  # too many wavelengths
        # looks weird, but just unpacks that single-item wavelength set
        [cwl] = wavelengths
        # and find the mean of the fwhms
        return cwl, np.mean([t[1] for t in wavelengthsAndFWHMs])

    def wavelength(self, channelNumber):
        """return wavelength if all sources in channel are of the same wavelength, else -1."""
        cwl, fwhm = self.wavelengthAndFWHM(channelNumber)
        return cwl

    def wavelengthBand(self, cwl):
        """Try to find the index of the band in the image which is closest to the given centre wavelength,
        disregarding bands with no wavelength or multiple wavelengths."""
        # first, get dict of wavelength and fwhm by channel.
        wavelengthAndFHWMByChan = {i: self.wavelengthAndFWHM(i) for i in range(self.channels)}
        # now get list of (index, distance from cwl, fwhm), filtering out multi-wavelength channels (for which
        # wavelength() returns -1)
        wavelengthAndFHWMByChan = [(k, abs(v[0] - cwl), v[1]) for k, v in wavelengthAndFHWMByChan.items() if v[0] >= 0]
        if len(wavelengthAndFHWMByChan) > 0:
            # now sort that list by CWL distance and then negative FWHM (widest first)
            wavelengthAndFHWMByChan.sort(key=lambda v: (v[1], -v[2]))
            closest = min(wavelengthAndFHWMByChan, key=lambda v: (v[1], -v[2]))
            return closest[0]  # return index
        else:
            # No wavelengths found ,return -1
            return -1

    def namedFilterBand(self, name):
        """Try to find the index of the first band in the image which has the filterName provided"""
        for i, s in enumerate(self.sources.sourceSets):
            # we are looking for a band in which ANY of the sources has the given name
            if s.matches(filterNameOrCWL=name, all_match=False):
                return i
        return -1

    def drawAnnotationsAndROIs(self, p: QPainter,
                        scale: float,
                        mapcoords: Callable[[float, float], Tuple[float, float]],
                        onlyROI: Union[ROI, Sequence] = None):
        """Draw annotations and ROIs onto a painter (either in a canvas or an output device.
        Will save and restore font because we might be doing font resizing"""

        oldFont = p.font()
        p.setFont(annotFont)

        if onlyROI is None:
            rois = self.rois
        elif isinstance(onlyROI, Sequence):
            rois = onlyROI
        else:
            rois = [onlyROI]

        for ann in self.annotations+rois:
            ann.annotate(p, scale, mapcoords)

        p.setFont(oldFont)
