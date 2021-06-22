## @package pancamimage
# Classes to encapsulate an image data cube which can be any number of channels
# and also incorporates region-of-interest data.  Conversions to and from float are
# done in many operations. Avoiding floats saves memory and speeds things up,
# but we could change things later.
import math
import numbers

import cv2 as cv
import numpy as np

from pcot.channelsource import IChannelSource, FileChannelSourceRed, FileChannelSourceGreen, FileChannelSourceBlue
from typing import List, Set, Optional
from rois import ROI, ROIPainted


## this is the parts of an image cube which are covered by the active ROIs
# in that image. It consists of
# * the image cropped to the bounding box of the ROIs. NOTE THAT this
#   is a VIEW INTO THE ORIGINAL IMAGE
# * the data for that bounding box in the image (x,y,w,h)
# * a boolean mask the same size as the BB, True for pixels which
#   should be manipulated in any operation.

class SubImageCubeROI:
    def __init__(self, img, imgToUse=None, roi=None):  # can take another image to get rois from
        rois = img.rois if imgToUse is None else imgToUse.rois
        self.channels = img.channels

        if roi is not None:
            rois = [roi]

        if len(rois) > 0:
            # construct a temporary ROI union
            roi = ROI.roiUnion(rois)
            self.bb = roi.bb()
            self.mask = roi.mask()
            x, y, w, h = self.bb
            self.img = img.img[y:y + h, x:x + w]

            if self.img.shape[:2] != self.mask.shape:
                raise Exception(
                    "Mask not same shape as image: can happen when ROI is out of bounds. Have you loaded a new image?")
        else:
            self.img = np.copy(img.img)  # make a copy to avoid descendant nodes changing their input nodes' outputs
            self.bb = (0, 0, img.w, img.h)  # whole image
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

    # generate a default mapping
    def generateDefaultMapping(self, img):
        if img.defaultMapping is not None:
            self.set(img.defaultMapping.red, img.defaultMapping.green, img.defaultMapping.blue)
        else:
            # TODO - do this properly, looking at filters
            self.red, self.green, self.blue = [img.channels - 1 if x >= img.channels else x for x in range(0, 3)]

    # generate a mapping from a new image if required - or keep using the old mapping
    # if we can.
    def ensureValid(self, img):
        # make sure there is a mapping, and that it's in range. If not, regenerate.
        if self.red < 0 or self.red >= img.channels or self.green >= img.channels or self.blue >= img.channels:
            self.generateDefaultMapping(img)

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


## an image - just a numpy array (the image) and a list of ROI objects. The array
# has shape either (h,w) (for a single channel) or (h,w,n) for multiple channels.
# Images are 32-bit float.
# An RGB mapping can be provided, saying how the image should be represented in RGB (via the rgb() method)
# There is also a list of source tuples, (filename,filter), indexed by channel.

class ImageCube:
    ## @var img
    # the numpy array containing the image data
    img: np.ndarray

    ## @var rois
    # the regions of interest
    rois: List[ROI]

    ## @var shape
    # the shape of the image array (i.e. the .shape field) - a single channel image will be a 2D array,
    # a multichannel image will be 3D.
    shape: np.ndarray

    ## @var channels
    # how many channels the image has.
    channels: int

    ## @var sources
    # a list of sets of sources - one set for each channel - describing where this data came from
    sources: List[Set[IChannelSource]]

    ## @var mapping
    # The RGB mapping to convert this image into RGB. May be None
    mapping: Optional[ChannelMapping]

    # create image from numpy array
    def __init__(self, img: np.ndarray, rgbMapping: ChannelMapping = None, sources: List[Set[IChannelSource]] = [],
                 defaultMapping: ChannelMapping = None):

        if img is None:
            raise Exception("trying to initialise image from None")
        self.img = img  # the image numpy array
        # first, check the dtype is valid
        if self.img.dtype != np.float32:
            raise Exception("Images must be floating point")
        self.rois = []  # no ROI
        self.shape = img.shape
        # set the image type
        if len(img.shape) == 2:
            # 2D image
            self.channels = 1
        else:
            self.channels = img.shape[2]
        self.w = img.shape[1]
        self.h = img.shape[0]
        # an image may have a list of source data attached to it indexed
        # by channel.
        # These are a list (for each channel) of sets of Source objects,
        # one for each filter. Thus each channel can come from more than one filter.
        #
        self.sources = sources
        self.defaultMapping = defaultMapping

        # get the mapping sorted, which may be None (in which case rgb() might not work).
        # Has to be done after the sources are set.
        self.mapping = None  # stops complaints...
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
    # If the source is None, use (fname,None) (i.e. no filter).
    # Always builds an RGB image.
    @classmethod
    def load(cls, fname, mapping, sources=None):
        print("ImageCube.load: " + fname)
        # imread with this argument will load any depth, any
        # number of channels
        img = cv.imread(fname, -1)
        if img is None:
            raise Exception('cannot read image {}'.format(fname))
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
        # build the default sources if required. This always builds an RGB image.
        if sources is None:
            sources = [{FileChannelSourceRed(fname)},
                       {FileChannelSourceGreen(fname)},
                       {FileChannelSourceBlue(fname)}]
        # and construct the image
        return cls(img, mapping, sources)

    # use this to get the sources when you are combining images channel-wise (i.e. where channel 0 is
    # combined with channel 0 in another image, and so on).

    @classmethod
    def buildSources(cls, images: List['ImageCube']):
        images = [x for x in images if x is not None]  # filter null images
        numChannels = max([x.channels for x in images])
        out = []
        for i in range(0, numChannels):
            s = set()
            for img in images:
                if i < len(img.sources):
                    s = set.union(s, img.sources[i])
            out.append(s)
        return out

    ## get a numpy image (not another ImageCube) we can display on an RGB surface - see
    # rgbImage if you want an imagecube. If there is more than one channel we need to have
    # an RGB mapping in the image. If showROIs is true, we create an image with the ROIs
    # on it. We can specify a different mapping than that of the image.
    def rgb(self, showROIs: bool = False, mapping: Optional[ChannelMapping] = None):
        # assume we're 8 bit
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

    ## as rgb, but wraps in an ImageCube. Also works out the sources, which should be for
    # the channels in the result. A different mapping from the image mapping can be specified.
    def rgbImage(self, mapping: Optional[ChannelMapping] = None):
        if mapping is None:
            mapping = self.mapping
        if mapping is None:
            raise Exception("trying to get rgb of an imagecube with no mapping")
        sources = [self.sources[mapping.red],
                   self.sources[mapping.green],
                   self.sources[mapping.blue]]
        # The RGB mapping here should be just [0,1,2], since this output is the RGB representation.
        return ImageCube(self.rgb(mapping=mapping), ChannelMapping(0, 1, 2), sources)

    ## save RGB representation
    def rgbWrite(self, filename):
        img = self.rgb()
        cv.imwrite(filename, img * 255)  # convert from 0-1

    def drawROIs(self, rgb: np.ndarray = None, onlyROI: ROI = None) -> np.ndarray:
        """Return an RGB representation of this image with any ROIs drawn on it - an image may be provided.
        onlyROI indicates that only one ROI should be drawn"""
        if rgb is None:
            rgb = self.rgb()

        if onlyROI is None:
            for r in self.rois:
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
        xx = ";".join([IChannelSource.stringForSet(x, 0) for x in self.sources])

        s += "src: [{}]".format(xx)
        x = [r.bb() for r in self.rois]
        x = [", ROI {},{},{}x{}".format(x, y, w, h) for x, y, w, h in x]
        s += "/".join(x) + ">"
        return s

    ## the descriptor is a string which can vary depending on main window settings.
    # If channel assignments are provided (e.g. [0,1,2]) select those channels and
    # show the descriptors for only those. Used in canvas. Not sure about it: on the one
    # hand we lose information (if we're viewing 3 channels from 11) but on the other hand
    # 11 channels is far too many to show in the descriptor at the bottom of the canvas!

    def getDesc(self, graph):
        if graph.doc.settings.captionType == 3:
            return ""
        out = [IChannelSource.stringForSet(s, graph.doc.settings.captionType) for s in self.sources]
        # if there are channel assignments, show only the assigned channels. Not sure about this.
        if self.mapping is not None:
            out = [out[x] for x in [self.mapping.red, self.mapping.green, self.mapping.blue]]
        desc = " ".join(["[" + s + "]" for s in out])
        return desc

    ## copy an image
    def copy(self):
        srcs = self.sources.copy()
        # it's probably best that this is a copy too - but if you notice
        # that you're changing the RGB mappings in a canvas and the image isn't changing,
        # it might be because of this.
        if self.mapping is not None:
            m = self.mapping.copy()
        else:
            m = None
        # we should be able to copy the default mapping reference OK, it won't change.
        i = ImageCube(self.img.copy(), m, srcs, defaultMapping=self.defaultMapping)
        i.rois = self.rois.copy()
        return i

    def hasROI(self):
        return len(self.rois) > 0

    ## return a copy of the image, with the given image spliced in at the
    # subimage's coordinates and masked according to the subimage
    def modifyWithSub(self, subimage: SubImageCubeROI, newimg: np.ndarray):
        i = self.copy()
        x, y, w, h = subimage.bb
        i.img[y:y + h, x:x + w][subimage.mask] = newimg[subimage.mask]
        return i

    ## given a wavelength, extract that wavelength's slice/image/channel and
    # build a new image with just that.
    def getChannelImageByWavelength(self, cwl):
        # for each channel's set of sources
        for i in range(len(self.sources)):  # iterate so we have the index
            x = self.sources[i]
            if len(x) == 1:
                # there must be only one source in the set; get it.
                item = next(iter(x))
                filt = item.getFilter()
                # there must be a filter in this source
                if filt is not None:
                    # and it must have a very close wavelength
                    if math.isclose(cwl, filt.cwl):
                        # now we have it. Extract that channel. Note - this is better than cv.split!
                        img = self.img[:, :, i]
                        return ImageCube(img, sources=[x])
        return None

    ## given a channel filter's name, extract that slice/image/channel and
    # build a new image with just that.
    def getChannelImageByName(self, name):
        # for each channel's set of sources
        for i in range(len(self.sources)):  # iterate so we have the index
            x = self.sources[i]
            if len(x) == 1:
                # there must be only one source in the set; get it.
                item = next(iter(x))
                # match either the filter name or position, case-dependent
                iname = item.getFilterName()
                ipos = item.getFilterPos()
                if iname == name or ipos == name:
                    # now we have it. Extract that channel. Note - this is better than cv.split!
                    img = self.img[:, :, i]
                    return ImageCube(img, sources=[x])
        return None

    ## annoyingly similar to the two methods above, this is used to get a channel _index_.
    def getChannelIdx(self, nameOrCwl):
        for i in range(len(self.sources)):  # iterate so we have the index
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
                raise Exception("All three RGB channel IDs or none must be provided in setDefaultMapping")

            ridx = self.getChannelIdx(r)
            if ridx is None:
                raise Exception("cannot find channel {}".format(r))
            gidx = self.getChannelIdx(g)
            if gidx is None:
                raise Exception("cannot find channel {}".format(g))
            bidx = self.getChannelIdx(b)
            if bidx is None:
                raise Exception("cannot find channel {}".format(b))

            self.mapping = ChannelMapping(ridx, gidx, bidx)
        else:
            self.mapping = ChannelMapping()

        self.mapping.ensureValid(self)
