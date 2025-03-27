"""Classes to encapsulate an image data cube which can be any number of channels
and also incorporates region-of-interest data.  Conversions to and from float are
done in many operations. Avoiding floats saves memory and speeds things up,
but we could change things later.
"""
import itertools
import logging

import os.path
from collections.abc import Iterable
from typing import List, Optional, Tuple, Sequence, Union

import cv2 as cv
import numpy as np
from PySide2.QtGui import QPainter
from tifffile.geodb import Datum

import pcot
from pcot import dq, ui
from pcot.documentsettings import DocumentSettings
from pcot.rois import ROI, ROIBoundsException
from pcot.sources import MultiBandSource, SourcesObtainable, Source
from pcot.utils import annotations
from pcot.utils.annotations import annotFont
from pcot.utils import image
from pcot.utils.archive import FileArchive
from pcot.utils.geom import Rect
import pcot.dq
from pcot.value import Value

logger = logging.getLogger(__name__)


class SubImageCube:
    """This is a class representing the parts of an imagecube which are covered by ROIs or an ROI.
    It consists of
    * the image cropped to the bounding box of the ROIs; this is a view into the original image.
    * the data for the BB (x,y,w,h)
    * uncertainty and DQ too
    * a boolean mask the same size as the BB, True for pixels contained in the ROIs and which
      should be manipulated.
    """

    def __init__(self, img, imgToUse=None, roi: Optional[ROI] = None, clip=True):
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
            try:
                roi = ROI.roiUnion(rois)
            except TypeError as e:
                print("Argh!")
                ROI.roiUnion(rois)
                raise e
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
                self.dq = img.dq[y:y + h, x:x + w]
                self.uncertainty = img.uncertainty[y:y + h, x:x + w]

                if self.img.shape[:2] != self.mask.shape:
                    raise Exception("Internal error: shape still incorrect after clip")

        if genFullImage:
            # here we just make a copy of the image
            self.img = np.copy(img.img)  # make a copy to avoid descendant nodes changing their input nodes' outputs
            self.dq = np.copy(img.dq)
            self.uncertainty = np.copy(img.uncertainty)
            self.bb = Rect(0, 0, img.w, img.h)  # whole image
            self.mask = np.full((img.h, img.w), True)  # full mask

    def fullmask(self, maskBadPixels=False):
        """the main mask is just a single channel - this will generate a mask
        of the same number of channels, so an x,y image will make an x,y mask
         and an x,y,n image will make an x,y,n mask.
         It will also optionally remove BAD bits from the mask, as indicated by the DQ array.
        """

        # so at this point the mask is (x,y).

        if len(self.img.shape) == 2:
            mask = self.mask  # the existing mask is fine
        else:
            h, w, chans = self.img.shape
            # flatten and repeat each element for each channel
            x = np.repeat(np.ravel(self.mask), chans)
            # put into a h,w,chans array
            mask = np.reshape(x, (h, w, chans))

        # now the mask is (x,y) for a 2-chan image or (x,y,n) for an n-channel image. We can
        # remove the bad bits if required

        if maskBadPixels:
            # make another mask out of the DQ bits, selecting any pixels with "bad" bits
            badmask = (self.dq & pcot.dq.BAD).astype(bool)
            # Negate that mask - it shows the bad pixels but we only want it to be
            # true where the good pixels are - then AND it into the main mask
            return mask & ~badmask
        return mask

    def masked_all(self, maskBadPixels=False, noDQ=False):
        """Return all the data masked by the ROI. This is a tuple of three masked arrays:
        the means (i.e. the image), the uncertainty and the DQ. The mask is the same for all three.
        If noDQ is set, only means and uncertainty are returned.
        """
        mask = self.fullmask(maskBadPixels)
        if noDQ:
            return (np.ma.masked_array(self.img, mask=~mask),
                    np.ma.masked_array(self.uncertainty, mask=~mask)
                    )
        else:
            return (np.ma.masked_array(self.img, mask=~mask),
                    np.ma.masked_array(self.uncertainty, mask=~mask),
                    np.ma.masked_array(self.dq, mask=~mask)
                    )

    def masked(self, maskBadPixels=False):
        """get the masked image as a numpy masked array (see also masked_all)"""
        return np.ma.masked_array(self.img, mask=~self.fullmask(maskBadPixels=maskBadPixels))

    def maskedDQ(self, maskBadPixels=False):
        """get the masked DQ as a numpy masked array (see also masked_all)"""
        return np.ma.masked_array(self.dq, mask=~self.fullmask(maskBadPixels=maskBadPixels))

    def maskedUncertainty(self, maskBadPixels=False):
        """get the masked uncertainty as a numpy masked array (see also masked_all)"""
        return np.ma.masked_array(self.uncertainty, mask=~self.fullmask(maskBadPixels=maskBadPixels))

    def cropother(self, img2):
        """use this ROI to crop the image in img2. Doesn't do masking, though.
        Copies the sources list from that image."""
        x, y, w, h = self.bb
        return ImageCube(img2.img[y:y + h, x:x + w], img2.mapping, img2.sources,
                         dq=img2.dq[y:y + h, x:x + w],
                         uncertainty=img2.uncertainty[y:y + h, x:x + w]
                         )

    def sameROI(self, other):
        """Compare two subimages - just their regions of interest, not the actual image data
        Will also work if the images are different depths."""
        return self.bb == other.bb and self.mask == other.mask

    def pixelCount(self):
        """How many pixels in the masked subimage? This does not take BAD bits into account,
        because different bands may have different bad bits."""
        return self.mask.sum()

    def setROI(self, img, roi):
        """Change the ROI of the subimage to be an ROI inside another
        image while keeping the subimage the same size (clipping it
        to the bounds of the new image). Sounds weird, but it used when
        we take a subimage and paste it into a different image, as in
        gradient offsetting."""

        bb = roi.bb()

        self.bb = bb.copy()
        imgBB = (0, 0, img.w, img.h)
        # get intersection of ROI BB and image BB.
        # SOME CODE DUPLICATION with __init__
        intersect = self.bb.intersection(imgBB)
        if intersect is None:
            # no intersection, ROI outside image
            raise ROIBoundsException()
        if intersect != self.bb:
            # intersection is not equal to ROI BB, we must clip
            roi = roi.clipToImage(img)
            self.bb = roi.bb()
            self.mask = roi.mask()

        x, y, w, h = self.bb  # this works even though self.bb is Rect
        self.img = img.img[y:y + h, x:x + w]
        self.dq = img.dq[y:y + h, x:x + w]
        self.uncertainty = img.uncertainty[y:y + h, x:x + w]


class ChannelMapping:
    """A mapping from a multichannel image into RGB. All nodes have one of these, although some may have more
    and some might not even use this one. That's because most (or at least many) nodes generate a single image and
    show it in their tab. Ideally, I should create one of these in just those nodes but I'm lazy.
    """

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

            # FINALLY, finally, finally - it could still happen that all the bands are the same
            # despite there being more than one channel (e.g. a monochrome image mapped to RGB).
            if self.red == self.green and self.green == self.blue:
                self.red, self.green, self.blue = [x % img.channels for x in range(0, 3)]

    def ensureValid(self, img):
        """generate a mapping from a new image if required - or keep using the old mapping
        if we can. Return self, for fluent."""
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


def load_rgb_image(fname, bitdepth=None) -> np.ndarray:
    """This is used by ImageCube to load its image data. It's a function because it's
    also used by the multifile loader."""
    fname = str(fname)  # fname could potentially be some kind of Path object.
    # imread with this argument will load any depth, any
    # number of channels
    img = cv.imread(fname, -1)
    if img is None:
        raise Exception(f'Cannot read file {fname}')
    if len(img.shape) == 2:  # expand to RGB. Annoyingly we cut it down later sometimes.
        img = image.imgmerge((img, img, img))
    # get the scaling factor, which depends on the bitdepth if one is provided, or will be the full bitdepth of
    # the image if not.
    if bitdepth is not None:
        scale = 2 ** bitdepth - 1
    elif img.dtype == np.uint8:
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
    return img


class ImageCube(SourcesObtainable):
    """
    an image - just a numpy array (the image) and a list of ROI objects. The array
    has shape either (h,w) (for a single channel) or (h,w,n) for multiple channels.
    Images are 32-bit float.
    An RGB mapping can be provided, saying how the image should be represented in RGB (via the rgb() method)
    There is also a MultiBandSource describing the source sets associated with each channel.
    """
    # the numpy arrays containing the image data, the uncertainty data and the data quality bit data
    img: np.ndarray  # H x W x Depth, float32
    uncertainty: np.ndarray  # H x W x Depth, float32
    dq: np.ndarray  # H x W x Depth, uint16

    # the regions of interest - these are also annotations! They are in a separate list
    # so they can be passed through or removed separately.
    rois: List[ROI]

    ## list of annotations - things that can be drawn on an image.
    annotations: List[annotations.Annotation]

    # the shape of the image array (i.e. the .shape field) - a single channel image will be a 2D array,
    # a multichannel image will be 3D.
    shape: Tuple

    # how many channels the image has.
    channels: int

    # a list of sets of sources - one set for each channel - describing where this data came from
    sources: MultiBandSource

    # The RGB mapping to convert this image into RGB. May be None
    mapping: Optional[ChannelMapping]

    def __init__(self, img: np.ndarray,
                 rgbMapping: ChannelMapping = None,
                 sources: MultiBandSource = None,
                 rois=None,
                 defaultMapping: ChannelMapping = None,
                 uncertainty=None, dq=None
                 ):
        """create imagecube from numpy array. Other fields are optional.
            image:          input numpy array: float32, Height x Width x Depth
            rgbMapping:     where the image stores its mapping. If None, it will use its own storage - but it
                            might also be a reference to an rgbMapping stored in a node or even from
                            another image; typically done because the node stores the rgbMapping
            sources:        a MultiBandSource, a wrapper around an array of sets of sources. If None, empty source sets
                            will be created
            rois:           a list of regions of interest, if None, an empty list will be created
            defaultMapping: a ChannelMapping object; this is consulted when we "guess RGB" - if it's not there,
                            we do genuinely guess (intelligently).
            uncertainty:    a float32 numpy array of the same dimensions as the image. If None, a zero array is created.
                            (but see dq below)
            dq:             data quality bits, a 16-bit unsigned int array of the same shape as the image.
                            If None, a zero array is created - but if a zero array is used (or created) for
                            uncertainty, the "no uncertainty data" bit is set on all pixels.

        """

        def cvt1channel(x):
            ## convert array of the form(x,y,1) to just (x,y)
            if len(x.shape) == 3 and x.shape[-1] == 1:
                return image.imgsplit(x)[0]
            else:
                return x

        if img is None:
            raise Exception("trying to initialise image from None")

        # first, check the dtype is valid
        if img.dtype != np.float32:
            raise Exception("Images must be 32-bit floating point")
        img = cvt1channel(img)  # convert (h,w,1) to (h,w)
        if rois is None:
            self.rois = []  # no ROI
        else:
            self.rois = rois
        self.annotations = []  # and no annotations
        self.shape = img.shape
        # set the image type
        if len(img.shape) == 2:
            # 2D image
            self.channels = 1
        elif len(img.shape) == 3:
            self.channels = img.shape[2]
        else:
            raise Exception("Images must be 3-dimensional arrays")

        # image should now be correct, set it into the object.

        self.img = img
        self.w = img.shape[1]
        self.h = img.shape[0]

        # an image may have a list of source data attached to it indexed by channel. Or if none is
        # provided, an empty one.
        if sources is not None:
            if not isinstance(sources, MultiBandSource):
                raise Exception("Image sources must be MultiBandSource")
            self.sources = sources
        else:
            self.sources = MultiBandSource.createEmptySourceSets(self.channels)

        self.defaultMapping = defaultMapping

        # get the mapping sorted, which may be None (in which case rgb() might not work).
        # Has to be done after the sources are set.
        if rgbMapping is None:
            rgbMapping = ChannelMapping().ensureValid(self)

        self.setMapping(rgbMapping)

        # bits we are going to set on every pixel's DQ data
        dqOnAllPixels = 0

        # uncertainty data
        if uncertainty is None:
            uncertainty = np.zeros(img.shape, dtype=np.float32)
            dqOnAllPixels |= pcot.dq.NOUNCERTAINTY
        uncertainty = cvt1channel(uncertainty)
        if uncertainty.dtype != np.float32:
            raise Exception("uncertainty data must be 32-bit floating point")
        if uncertainty.shape != img.shape:
            raise Exception("uncertainty data is not same shape as image data")

        self.uncertainty = uncertainty

        # DQ data
        if dq is None:
            dq = np.zeros(img.shape, dtype=np.uint16)
        if dq.dtype != np.uint16:
            raise Exception("DQ data is not 16-bit unsigned integers")
        dq = cvt1channel(dq)
        if dq.shape != img.shape:
            raise Exception("DQ data is not same shape as image data")

        dq |= dqOnAllPixels
        self.dq = dq

    def setMapping(self, mapping: ChannelMapping):
        """Set the RGB mapping for this image, and create default channel mappings if necessary."""
        self.mapping = mapping
        if mapping is not None:
            mapping.ensureValid(self)
        return self

    ## class method for loading an image (using cv's imread)
    # Always builds an RGB image. Sources must be provided.
    @classmethod
    def load(cls, fname, mapping, sources, bitdepth=None):
        logger.info(f"ImageCube load: {fname}")
        img = load_rgb_image(fname, bitdepth=bitdepth)
        # create sources if none given
        if sources is None:
            sources = MultiBandSource([Source().setBand('R'),
                                       Source().setBand('G'),
                                       Source().setBand('B')])
        # and construct the image
        return cls(img, mapping, sources)

    def rgb(self, mapping: Optional[ChannelMapping] = None) -> np.ndarray:
        """get a numpy image (not another ImageCube) we can display on an RGB surface - see
        rgbImage if you want an imagecube. If there is more than one channel we need to have
        an RGB mapping in the image."""

        if self.channels == 1:
            # single channel images are a special case, rather than
            # [chans,w,h] they are just [w,h]
            return image.imgmerge([self.img, self.img, self.img])
        else:
            if mapping is None:
                mapping = self.mapping
            if mapping is None:
                raise Exception("trying to get rgb of an imagecube with no mapping")
            red = self.img[:, :, mapping.red]
            green = self.img[:, :, mapping.green]
            blue = self.img[:, :, mapping.blue]
        img = image.imgmerge([red, green, blue])
        return img

    def rgbImage(self, mapping: Optional[ChannelMapping] = None) -> 'ImageCube':
        """as rgb, but wraps in an ImageCube. Also works out the sources, which should be for
        the channels in the result. A different mapping from the image mapping can be specified.
        Quite a bit of code duplication here from rgb() but it can't really be helped."""

        if self.channels == 1:
            unc = np.dstack([self.uncertainty, self.uncertainty, self.uncertainty])
            dq = np.dstack([self.dq, self.dq, self.dq])
            img = np.dstack([self.img, self.img, self.img])
        else:
            if mapping is None:
                mapping = self.mapping
            if mapping is None:
                raise Exception("trying to get rgbImage of an imagecube with no mapping")
            img = np.dstack([
                self.img[:, :, mapping.red],
                self.img[:, :, mapping.green],
                self.img[:, :, mapping.blue]]
            )
            dq = np.dstack([
                self.dq[:, :, mapping.red],
                self.dq[:, :, mapping.green],
                self.dq[:, :, mapping.blue]]
            )
            unc = np.dstack([
                self.uncertainty[:, :, mapping.red],
                self.uncertainty[:, :, mapping.green],
                self.uncertainty[:, :, mapping.blue]]
            )
        # The RGB mapping here should be just [0,1,2], since this output is the RGB representation.
        return ImageCube(img, ChannelMapping(0, 1, 2), self.rgbSources(mapping),
                         dq=dq, uncertainty=unc,
                         rois=self.rois)

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

    ## extract the "subimage" - the image cropped to regions of interest,
    # with a mask for those ROIs. Note that you can also supply an image,
    # in which case you get this image cropped to the other image's ROIs!
    # You can also limit to a single ROI or use all of them (the default)
    def subimage(self, imgToUse=None, roi=None):
        return SubImageCube(self, imgToUse, roi)

    def __repr__(self):
        """simple string representation - should probably have no newlines in it. I've deliberately made it look a bit
        line an HTML tag, for no very good reason."""

        s = "<Image-{} {}x{} array:{} channels:{}, {} bytes, ".format(id(self), self.w, self.h,
                                                                      str(self.img.shape), self.channels,
                                                                      self.img.nbytes)

        s += "src: [{}]".format(self.sources.brief())
        rois = ";".join([str(r) for r in self.rois])
        s += rois + ">"
        return s

    def __str__(self):
        """Prettier string representation - but (importantly) doesn't have a unique ID so we can use it
        in string tests."""
        s = f"Image {self.w}x{self.h}x{self.channels} {self.img.nbytes} bytes"

        s += "\nsrc: [{}]".format(self.sources.brief())
        if len(self.rois) > 0:
            s += "\n" + "\n".join([str(r) for r in self.rois])
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

    def shallowCopy(self, copyAnnotations=True):
        """Create a shallow copy - this points to the same image data and same mapping data, but allows
        it to be changed later.

        We still copy sources, ROIs and annotations, in the latter case making shallow copies of those lists.

        Sometimes a node reads an image from a parent node, and then changes the image's mapping - changing
        it for the parent node too and decoupling the mapping in the image from that parent node, which causes
        problems if the parent node has tab open. Typical symptom: changing RGB mapping in the parent's tab has
        no effect because the mapping used in the canvas (the parent node's mapping) has become uncoupled from
        the mapping the displayed image is using (which was changed to the child node's mapping).

        See Issue #56 for this.
        """
        i = ImageCube(self.img,
                      self.mapping,
                      self.sources.copy(),
                      defaultMapping=self.defaultMapping,
                      uncertainty=self.uncertainty,
                      dq=self.dq)
        i.rois = self.rois.copy()
        if copyAnnotations:
            i.annotations = self.annotations.copy()
        return i

    def copy(self, keepMapping=False, copyAnnotations=True):
        """copy an image. If keepMapping is false, the image mapping will also be a copy. If true, the mapping
        is a reference to the same mapping as in the original image.

        If you notice that you're changing the RGB mappings in a canvas and the image isn't changing,
        it might be because of this.

        But it also might be because a child node is reading an image and changing its mapping to its own
        node mapping, which means that it also changes for the parent node - because the child node isn't making
        a copy of the image! If you want to make a shallow copy of the image, use shallowCopy.

        """
        if self.mapping is None or keepMapping:
            m = self.mapping
        else:
            m = self.mapping.copy()

        srcs = self.sources.copy()

        # we should be able to copy the default mapping reference OK, it won't change.
        i = ImageCube(self.img.copy(), m, srcs, defaultMapping=self.defaultMapping,
                      uncertainty=self.uncertainty.copy(),
                      dq=self.dq.copy())
        i.rois = self.rois.copy()
        if copyAnnotations:
            i.annotations = self.annotations.copy()
        return i

    def hasROI(self):
        return len(self.rois) > 0

    def modifyWithSub(self, subimage: SubImageCube, newimg: np.ndarray,
                      sources=None, keepMapping=False,
                      dqv=None, dqOR=np.uint16(0), uncertainty=None,
                      dontWriteBadPixels=False
                      ) -> 'ImageCube':
        """return a copy of the image, with the given image spliced in at the subimage's coordinates and masked
        according to the subimage. keepMapping will ensure that the new image has the same mapping as the old.

        There are some ... complexities involving DQ and uncertainty.

        If no uncertainty is provided, the uncertainty in the result will be zero and NOUNCERTAINTY will be set
        in the DQ bits.

        DQ can either be set by passing in dqv (value or array), or a value or array can be provided to OR in.
        """

        i = self.copy(keepMapping)
        x, y, w, h = subimage.bb
        # we only want to paste into the bits in the image that are covered
        # by the mask - and we want the full mask
        mask = subimage.fullmask(maskBadPixels=dontWriteBadPixels)

        # if the dq we're going to OR in isn't a scalar, make it fit the mask.
        if not np.isscalar(dqOR):
            dqOR = dqOR[mask]

        if newimg is not None:
            # copy the new image bits in
            i.img[y:y + h, x:x + w][mask] = newimg[mask]
        if uncertainty is not None:
            # if uncertainty is provided copy that in
            i.uncertainty[y:y + h, x:x + w][mask] = uncertainty[mask]
        else:
            # if no uncertainty data is provided, set the uncertainty to zero and also OR in a NOUNCERTAINTY flag
            i.uncertainty[y:y + h, x:x + w][mask] = 0
            dqOR |= dq.NOUNCERTAINTY

        if dqv is not None:
            # DQ data is provided - make sure it fits the mask and then combine with the dqOR bits
            # to generate the new DQ data
            if not np.isscalar(dqv):
                dqv = dqv[mask]
            i.dq[y:y + h, x:x + w][mask] = dqv | dqOR
        else:
            # No DQ data is provided, just OR in the dqOR bits
            i.dq[y:y + h, x:x + w][mask] |= dqOR

        # can replace sources if required
        if sources is not None:
            i.sources = sources
        return i

    def getChannelImageByFilter(self, filterNameOrCWL):
        """Given a filter name, position or CWL, get a list of all channels which use it. Then build an image
        out of those channels. Usually this returns a single channel image, but it could very easily not. If this is
        being called from the $ operator, that operator raise an error if this method produces more than one channel.
        """

        # get list of matching channel indices (often only one). If a single wavelength or filtername is provided
        # we should turn that into a list of one element. The test here is like it is because strings are
        # also iterable.

        if not isinstance(filterNameOrCWL, Iterable) or isinstance(filterNameOrCWL, str):
            filterNameOrCWL = [filterNameOrCWL]  # might get some kind of iterable, or just a bare value
        lstOfChannels = [self.sources.search(filterNameOrCWL=x) for x in list(filterNameOrCWL)]
        lstOfChannels = list(itertools.chain.from_iterable(lstOfChannels))  # flatten the list-of-lists we got
        if len(lstOfChannels) == 0:
            return None  # no matches found
        chans = []
        sources = []
        dqs = []
        uncertainties = []

        # now create a list of source sets and a list of single channel images
        for i in lstOfChannels:
            sources.append(self.sources.sourceSets[i])
            if self.channels == 1:
                # sometimes I really regret not making single band images (h,w,1) shape. This is one of those times.
                chans.append(self.img)
                dqs.append(self.dq)
                uncertainties.append(self.uncertainty)
            else:
                chans.append(self.img[:, :, i])
                dqs.append(self.dq[:, :, i])
                uncertainties.append(self.uncertainty[:, :, i])

        if len(lstOfChannels) == 1:
            # single channel case
            img = chans[0]
            dqs = dqs[0]
            uncertainties = uncertainties[0]
        else:
            # else create a new multichannel image
            img = np.stack(chans, axis=-1)
            dqs = np.stack(dqs, axis=-1)
            uncertainties = np.stack(uncertainties, axis=-1)
        # and a new imagecube
        return ImageCube(img, sources=MultiBandSource(sources), uncertainty=uncertainties, dq=dqs)

    ## crop an image down to its regions of interest.
    def cropROI(self):
        subimg = self.subimage()
        img = ImageCube(subimg.img,
                        uncertainty=subimg.uncertainty,
                        dq=subimg.dq,
                        rgbMapping=self.mapping, defaultMapping=self.defaultMapping, sources=self.sources)
        img.rois = [roi.rebase(subimg.bb.x, subimg.bb.y) for roi in self.rois]
        #        img.rois = [ROIPainted(subimg.mask, "crop")]
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

        def encodeArrayValue(e):
            # return value as tuple - if bool is true we compressed the array down to a single
            # value and store shape and type data too
            v = e.ravel()[0]
            return (True, float(v), e.shape, str(e.dtype)) if np.all(e == v) else (False, e, None, None)

        return {
            'data': self.img,
            'mapping': self.mapping.serialise(),
            'defmapping': self.defaultMapping.serialise() if self.defaultMapping else None,
            'sources': self.sources.serialise(),
            'dq': encodeArrayValue(self.dq),
            'uncertainty': encodeArrayValue(self.uncertainty)
        }

    @classmethod
    def deserialise(cls, d):
        """Inverse of serialise(), requires a document to get the inputs"""

        def decodeArrayValue(tup):
            isAllSame, v, shape, tp = tup
            if isAllSame:
                v = np.full(shape, v, dtype=np.dtype(tp))
            return v

        data = d['data']  # should already have been converted into an ndarray
        mapping = ChannelMapping.deserialise(d['mapping'])
        defmapping = None if d['defmapping'] is None else ChannelMapping.deserialise(d['defmapping'])
        sources = MultiBandSource.deserialise(d['sources'])

        dq = decodeArrayValue(d['dq']) if 'dq' in d else None
        uncertainty = decodeArrayValue(d['uncertainty']) if 'uncertainty' in d else None

        return cls(data, rgbMapping=mapping, sources=sources, defaultMapping=defmapping,
                   uncertainty=uncertainty, dq=dq)

    def filter(self, channelNumber):
        """Get the filter for a channel if all sources have the same filter, else None. Compare with
        wavelength() and wavelengthAndFWHM() below."""
        # get the SourceSet
        sources = self.sources.sourceSets[channelNumber]
        # all sources in this channel should have a filter
        sources = [s for s in sources.sourceSet if s.getFilter()]
        # all the sources in this channel should have the same filter
        filters = set([s.getFilter() for s in sources])
        if len(filters) != 1:
            return None
        # return the only item in that set
        [f] = filters
        return f

    def wavelengthAndFWHM(self, channelNumber):
        """get cwl and mean fwhm for a channel if all sources have the same filter, else -1. Compare with
        wavelength() below."""
        f = self.filter(channelNumber)
        if f is None:
            return -1, -1
        else:
            return f.cwl, f.fwhm

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
            closest = wavelengthAndFHWMByChan[0]  # we return "index", the first item in the first tuple
            #            closest = min(wavelengthAndFHWMByChan, key=lambda v: (v[1], -v[2]))
            return closest[0]
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

    def _getROIList(self, onlyROI: Union[ROI, Sequence]):
        """Get a list of ROIs to process, from either our ROI (if none) or a list or
        single ROI"""
        if onlyROI is None:
            rois = self.rois
        elif isinstance(onlyROI, Sequence):
            rois = onlyROI
        else:
            rois = [onlyROI]
        return rois

    def drawAnnotationsAndROIs(self, p: QPainter,
                               onlyROI: Union[ROI, Sequence] = None,
                               inPDF: bool = False,
                               alpha: float = 1.0):
        """Draw annotations and ROIs onto a painter (either in a canvas or an output device).
        Will save and restore font because we might be doing font resizing"""

        oldFont = p.font()
        p.setFont(annotFont)

        rois = self._getROIList(onlyROI)

        if inPDF:
            for ann in self.annotations + rois:
                ann.annotatePDF(p, self)
        else:
            for ann in self.annotations + rois:
                ann.annotate(p, self, alpha=alpha)

        p.setFont(oldFont)

    def __getitem__(self, pixTuple):
        """get a Value (or tuple of Values for a multiband image) containing a pixel. Takes x,y."""
        x, y = pixTuple
        ns = self.img[y, x]
        us = self.uncertainty[y, x]
        ds = self.dq[y, x]

        if self.channels == 1:
            return Value(ns, us, ds)
        else:
            return tuple([Value(n, u, d) for (n, u, d) in zip(ns, us, ds)])

    def countBadPixels(self):
        if self.channels == 1:
            d = self.dq
        else:
            d = np.bitwise_or.reduce(self.dq, axis=2)
        return np.count_nonzero(d & dq.BAD)

    def rotate(self, angleDegrees):
        """Rotate the image by the given angle (in degrees), returning a new image or None if the angle is not valid.
        Will return a copy of the image with the annotations and ROIs removed."""
        # first, make sure angleDegrees is positive and in range 0-360
        angleDegrees = angleDegrees % 360
        if angleDegrees % 90 != 0:
            return None
        # work out how many times we need to rotate 90 degrees
        n = int(angleDegrees / 90)
        # make a copy of the image and rotate its arrays in-place that many times
        img = self.copy()
        img.img = np.rot90(img.img, n)
        img.uncertainty = np.rot90(img.uncertainty, n)
        img.dq = np.rot90(img.dq, n)
        # remove all annotations and ROIs
        img.annotations = []
        img.rois = []
        # switch the w and h fields
        img.w, img.h = img.h, img.w

        return img

    def flip(self, vertical=True):
        """Flip an image horizontally or vertically. Returns a new image with annotations and ROIs removed."""
        img = self.copy()
        if vertical:
            img.img = np.flipud(img.img)
            img.uncertainty = np.flipud(img.uncertainty)
            img.dq = np.flipud(img.dq)
        else:
            img.img = np.fliplr(img.img)
            img.uncertainty = np.fliplr(img.uncertainty)
            img.dq = np.fliplr(img.dq)
        # remove all annotations and ROIs
        img.annotations = []
        img.rois = []
        return img

    def resize(self, w, h, method):
        """
        Resize the image using one the OpenCV methods.
        Note that we don't resize DQ. Instead, if any BAD bit is present in a channel it is propagated
        to all the bits in the channel.
        """
        try:
            outimg = cv.resize(self.img, (w, h), interpolation=method)
            outunc = cv.resize(self.uncertainty, (w, h), interpolation=method)
        except Exception as e:
            ui.log(str(e))
            raise Exception(f"OpenCV error - could not resize image")

        dqs = []
        if self.channels == 1:
            # dammit. Two cases because two different image formats.
            # OR together all the DQ bits in the channel
            badbits = np.bitwise_or.reduce(self.dq, axis=None) & pcot.dq.BAD
            outdq = np.full((h, w), badbits, dtype=np.uint16)
        else:
            dqs = []
            for i in range(self.channels):
                dqbits = self.dq[:, :, i]
                # OR together all the DQ bits in the channel
                badbits = np.bitwise_or.reduce(dqbits, axis=None) & pcot.dq.BAD
                dqbits = np.full((h, w), badbits, dtype=np.uint16)
                dqs.append(dqbits)
            outdq = np.stack(dqs, axis=-1)

        return ImageCube(outimg, self.mapping, self.sources, uncertainty=outunc, dq=outdq)

    def get_uncertainty_image(self):
        """Return an image with this image's uncertainty as its nominal values and zero uncertainty.
        Sources, mapping and ROIs are preserved.
        """
        return ImageCube(self.uncertainty, self.mapping, self.sources, rois=self.rois)

    def bands(self):
        """Return a list of the CWLs of the filters. If there are no filters on any of the bands, raise."""
        d = [self.wavelengthAndFWHM(i)[0] for i in range(self.channels)]
        if any([x == -1 for x in d]):
            raise Exception("bands property: Not all bands have a filter")
        return d

    def getROIByLabel(self, label):
        """Return an ROI given its label, or None if not found"""
        for r in self.rois:
            if r.label == label:
                return r
        return None

    def save(self, filename, annotations=False, format: str = None,
             name: str = None, description: str = "", append: bool = False,
             pixelWidth=None):
        """Write the image to a file, with or without annotations. If format is provided, it will be used
        otherwise the format will be inferred from the filename extension. Note that this will always clobber -
        determining if the file already exists must be handled by the caller.

        * annotations - add annotations if true (not PARC)
        * format - if not None, use this to determine the format, not the file extension
        * name - the name of the image (used in the PARC format)
        * description - a text description of the image (used in the PARC format)
        * append - if True, append to an existing PARC file, otherwise create a new PARC.
        * pixelWidth - if there are annotations, resize to this (default 1000) before saving.
        """

        from pcot import imageexport
        from pcot.utils.datumstore import DatumStore

        if format is None:
            if '.' not in filename:
                raise ValueError(f"No extension provided in filename {filename}")
            _, format = os.path.splitext(filename)
            format = format[1:]  # remove the dot
        elif '.' not in filename:
            filename += f".{format}"

        format = format.lower()

        if format != 'parc':
            if description is not None and description != "":
                raise ValueError("Description is not supported for image formats other than PARC")
            if append:
                raise ValueError("Append is not supported for image formats other than PARC")

        if format == 'pdf':
            imageexport.exportPDF(self, filename, annotations=annotations)
        elif format == 'svg':
            imageexport.exportSVG(self, filename, annotations=annotations)
        elif format in ('png', 'jpg', 'jpeg', 'bmp', 'tiff'):
            if annotations:
                imageexport.exportRaster(self, filename, annotations=annotations, pixelWidth=pixelWidth)
            else:
                # direct write with imwrite - this used to be its own method, rgbWrite()
                img = self.rgb()
                # convert to 8-bit integer from 32-bit float
                img8 = (img * 256).clip(max=255).astype(np.ubyte)
                # and change endianness
                img8 = cv.cvtColor(img8, cv.COLOR_RGB2BGR)
                cv.imwrite(filename, img8)
        elif format == 'parc':
            if name is None:
                raise ValueError("PARC format requires a name for the datum being saved (not just a filename)")
            if annotations:
                raise ValueError("PARC format does not support annotations")
            else:
                with FileArchive(filename, "a" if append else "w") as a:
                    from pcot.datum import Datum  # late import otherwise cyclic fun
                    ds = DatumStore(a)
                    ds.writeDatum(name, Datum(Datum.IMG, self), description)
        else:
            raise ValueError(f"Unsupported file format for image save: {format}")
