## @package pancamimage
# Classes to encapsulate an image data cube which can be any number of channels
# and also incorporates region-of-interest data.  Conversions to and from float are
# done in many operations. Avoiding floats saves memory and speeds things up,
# but we could change things later.

import cv2 as cv
import numpy as np
from channelsource import IChannelSource, FileChannelSourceRed, FileChannelSourceGreen, FileChannelSourceBlue

import filters





## definition of interface for regions of interest
class ROI:
    ## return a (x,y,w,h) tuple describing the bounding box for this ROI
    def bb(self):
        pass

    ## return an image cropped to the BB
    def crop(self, img):
        x, y, w, h = self.bb()
        return img.img[y:y + h, x:x + w]

    ## return a boolean mask which, when imposed on the cropped image,
    # gives the ROI. Or none, in which case there is no mask.
    def mask(self):
        pass


## a rectangle ROI

class ROIRect(ROI):
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def bb(self):
        return self.x, self.y, self.w, self.h

    def mask(self):
        # return a boolean array of True, same size as BB
        return np.full((self.h, self.w), True)

    def __str__(self):
        return "{} {} {}x{}".format(self.x, self.y, self.w, self.h)


## this is the parts of an image cube which are covered by the active ROIs
# in that image. It consists of
# * the image cropped to the bounding box of the ROIs. NOTE THAT this
#   is a VIEW INTO THE ORIGINAL IMAGE
# * the data for that bounding box in the image (x,y,w,h)
# * a boolean mask the same size as the BB, True for pixels which
#   should be manipulated in any operation.

class SubImageCubeROI:
    def __init__(self, img):
        if len(img.rois) > 0:
            bbs = [r.bb() for r in img.rois]  # get bbs
            x1 = min([b[0] for b in bbs])
            y1 = min([b[1] for b in bbs])
            x2 = max([b[0] + b[2] for b in bbs])
            y2 = max([b[1] + b[3] for b in bbs])
            self.bb = (x1, y1, x2 - x1, y2 - y1)
            self.img = img.img[y1:y2, x1:x2]
            # now construct the mask, initially all False
            self.mask = np.full((y2 - y1, x2 - x1), False)
            # and OR the ROIs into it
            for r in img.rois:
                # calculate ROI's position inside subimage
                x = r.x - x1
                y = r.y - y1
                # get ROI's mask
                roimask = r.mask()
                # add it at that position
                self.mask[y:y + r.h, x:x + r.w] = roimask
                # debugging code to let us see the submask
            #                xxx = self.mask.astype(np.ubyte)*255
            #                print(xxx)
            #                cv.imwrite("foo.png",cv.merge([xxx,xxx,xxx]))
            if self.img.shape[:2] != self.mask.shape:
                raise Exception(
                    "Mask not same shape as image: can happen when ROI is out of bounds. Have you loaded a new image?")
        else:
            self.img = img.img
            self.bb = (0, 0, img.w, img.h)  # whole image
            self.mask = np.full((img.h, img.w), True)  # full mask

    ## the main mask is just a single channel - this will generate a mask
    # of the same number of channels, so an x,y image will make an x,y mask
    # and an x,y,n image will make an x,y,n mask.
    def fullmask(self):
        if len(self.img.shape) == 2:
            return self.mask  # the existing mask is fine
        else:
            print("SPECIAL")
            h, w, chans = self.img.shape
            # flatten and repeat each element thrice
            x = np.repeat(np.ravel(self.mask), chans)
            # put into a h,w,3 array            
            return np.reshape(x, (h, w, chans))

    ## use this ROI to crop the image in img2. Doesn't do masking, though.
    # Copies the sources list from that image.
    def cropother(self, img2):
        x, y, w, h = self.bb
        return ImageCube(img2.img[y:y + h, x:x + w], img2.sources)


## an image - just a numpy array (the image) and a list of ROI objects. The array
# has shape either (h,w) (for a single channel) or (h,w,n) for multiple channels.
# In connections (see conntypes.py), single channel images are "imggrey" while
# multiple channels are "imgrgb" for RGB images (3 channels) or "imgstrange"
# for any other number of channels. Images are 32-bit float.
# There is also a list of source tuples, (filename,filter), indexed by channel.

class ImageCube:
    # create image from numpy array
    def __init__(self, img, sources=[]):
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

    #        if len(sources)==0:
    #            raise Exception("No source")

    ## class method for loading an image (using cv's imread)
    # If the source is None, use (fname,None) (i.e. no filter).
    # Always builds an RGB image.
    @classmethod
    def load(cls, fname, sources=None):
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
        print(sources)
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
        return cls(img, sources)

    # use this to get the sources when you are combining images channel-wise (i.e. where channel 0 is
    # combined with channel 0 in another image, and so on).

    @classmethod
    def buildSources(cls, images):
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

    ## get a numpy image (not another Image) we can display on an RGB surface
    def rgb(self):
        # assume we're 8 bit
        if self.channels == 1:
            return cv.merge([self.img, self.img, self.img])  # greyscale
        elif self.channels == 3:
            return self.img  # just fine as it is
        else:
            # well, now we have something weird. If there are fewer than three, there must 
            # be two - use red and blue. If there are more than three, just use the first three.
            chans = cv.split(self.img)
            if self.channels == 2:
                blk = np.zeros(self.img.shape[0:2]).astype(np.ubyte)
                return cv.merge([chans[0], blk, chans[1]])
            else:
                return cv.merge(chans[0:3])

    ## extract the "subimage" - the image cropped to regions of interest,
    # with a mask for those ROIs
    def subimage(self):
        return SubImageCubeROI(self)

    def __str__(self):
        s = "<Image {}x{} array:{} channels:{}, {} bytes, ".format(self.w, self.h,
                                                                   str(self.img.shape), self.channels, self.img.nbytes)
        xx = ";".join([IChannelSource.stringForSet(x, 0) for x in self.sources])  ## caption type 0 is filter positions only
        s += "src: [{}]".format(xx)
        x = [r.bb() for r in self.rois]
        x = [", ROI {},{},{}x{}".format(x, y, w, h) for x, y, w, h in x]
        s += "/".join(x) + ">"
        return s

    ## the descriptor is a string which can vary depending on main window settings

    def getDesc(self, mainwindow):
        if mainwindow.captionType == 3:
            return ""
        out = [IChannelSource.stringForSet(s, mainwindow.captionType) for s in self.sources]
        desc = " ".join(["[" + s + "]" for s in out])
        return desc

    ## copy an image
    def copy(self):
        srcs = self.sources.copy()
        i = ImageCube(self.img.copy(), srcs)
        i.rois = self.rois.copy()
        return i

    ## return a copy of the image, with the given image spliced in at the
    # subimage's coordinates and masked according to the subimage
    def modifyWithSub(self, subimage, newimg):
        i = self.copy()
        x, y, w, h = subimage.bb
        i.img[y:y + h, x:x + w][subimage.mask] = newimg[subimage.mask]
        return i
