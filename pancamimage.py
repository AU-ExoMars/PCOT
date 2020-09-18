import numpy as np
import cv2 as cv

# Classes to encapsulate an image which can be any number of channels
# and also incorporates region-of-interest data. At the moment, all images
# are 8-bit and any number of channels. Conversions to and from float are
# done in many operations. Avoiding floats saves memory and speeds things up,
# but we could change things later.

# definition of ROI interface
class ROI:
    # return a (x,y,w,h) tuple describing the bounding box for this ROI
    def bb(self):
        pass
    # return an image cropped to the BB
    def crop(self,img):
        x,y,w,h = self.bb()
        print("Cropping to ",x,y,w,h)
        return img.img[y:y+h,x:x+w]
    # return a boolean mask which, when imposed on the cropped image,
    # gives the ROI. Or none, in which case there is no mask.
    def mask(self):
        pass

                    
# a rectangle ROI
        
class ROIRect(ROI):
    def __init__(self,x,y,w,h):
        self.x=x
        self.y=y
        self.w=w
        self.h=h
    def bb(self):
        return (self.x,self.y,self.w,self.h)
    def mask(self):
        # return a boolean array of True, same size as BB
        return np.full((self.h,self.w),True)
    def __str__(self):
        return "{} {} {}x{}".format(self.x,self.y,self.w,self.h)

# this is the parts of an image which are covered by the active ROIs
# in that image. It consists of
# * the image cropped to the bounding box of the ROIs. NOTE THAT this
#   is a VIEW INTO THE ORIGINAL IMAGE
# * the data for that bounding box in the image (x,y,w,h)
# * a boolean mask the same size as the BB, True for pixels which
#   should be manipulated in any operation.

class SubImageROI:
    def __init__(self,img):
        if len(img.rois)>0:
            bbs = [r.bb() for r in img.rois] # get bbs
            x1 = min([b[0] for b in bbs])
            y1 = min([b[1] for b in bbs])
            x2 = max([b[0]+b[2] for b in bbs])
            y2 = max([b[1]+b[3] for b in bbs])
            self.bb = (x1,y1,x2-x1,y2-y1)
            self.img = img.img[y1:y2,x1:x2]
            # now construct the mask, initially all False
            self.mask = np.full((y2-y1,x2-x1),False)
            # and OR the ROIs into it
            for r in img.rois:
                # calculate ROI's position inside subimage
                x = r.x - x1
                y = r.y - y1
                # get ROI's mask
                roimask = r.mask()
                # add it at that position
                self.mask[y:y+r.h,x:x+r.w]=roimask
                # debugging code to let us see the submask
#                xxx = self.mask.astype(np.ubyte)*255
#                print(xxx)
#                cv.imwrite("foo.png",cv.merge([xxx,xxx,xxx]))
            if self.img.shape[:2] != self.mask.shape:
                raise Exception("Mask not same shape as image: can happen when ROI is out of bounds. Have you loaded a new image?")
        else:
            self.img = img.img
            self.bb = (0,0,img.w,img.h) # whole image
            self.mask = np.full((img.h,img.w),True) # full mask

    def fullmask(self):
        # the main mask is just a single channel. This will generate a mask
        # of the same number of channels, so an x,y image will make an x,y mask
        # and an x,y,3 image will make an x,y,3 mask.
        if len(self.img.shape)==2:
            return self.mask # the existing mask is fine
        else:
            h,w,chans = self.img.shape
            # flatten and repeat each element thrice
            x = np.repeat(np.ravel(self.mask),3) 
            # put into a h,w,3 array            
            return np.reshape(x,(h,w,3))

    def cropother(self,img2):
        # use this ROI to crop the image in img2. Doesn't do masking, though.
        x,y,w,h = self.bb
        return Image(img2.img[y:y+h,x:x+w])

# an image - just a numpy array (the image) and a list of ROI objects. The array 
# has shape either (h,w) (for a single channel) or (h,w,n) for multiple channels.
# In connections (see conntypes.py), single channel images are "imggrey" while
# multiple channels are "imgrgb" for RGB images (3 channels) or "imgstrange"
# for any other number of channels. Images are 32-bit float.

class Image:
    # create image from numpy array
    def __init__(self,img):
        if img is None:
            raise Exception("trying to initialise image from None")
        self.img = img # the image numpy array
        # first, check the dtype is valid
        if self.img.dtype != np.float32:
            raise Exception("Images must be floating point")
        self.rois = []  # no ROI
        self.shape = img.shape
        # set the image type
        if len(img.shape)==2:
            # 2D image
            self.channels=1
        else:
            self.channels=img.shape[2]
        self.w = img.shape[1]
        self.h = img.shape[0]
    
    # class method for loading an image (using cv's imread)
    @classmethod
    def load(cls,fname):
        # imread with this argument will load any depth, any
        # number of channels
        img = cv.imread(fname,-1) 
        if img is None:
            raise Exception('cannot read image {}'.format(fname))
        if len(img.shape)==2: # expand to RGB. Annoyingly we cut it down later sometimes.
            img = cv.merge((img,img,img))
        # get the scaling factor
        if img.dtype == np.uint8:
            scale = 255.0
        elif img.dtype == np.uint16:
            scale = 65535.0
        else:
            scale = 1.0
        # convert from BGR to RGB (OpenCV is weird)
        img = cv.cvtColor(img,cv.COLOR_BGR2RGB)
        # convert to floats (32 bit)
        img = img.astype(np.float32)
        # scale to 0..1 
        img /= scale
        # and construct the image
        return cls(img)        
        
    # get a numpy image (not another Image) we can display on an RGB surface
    def rgb(self):
        # assume we're 8 bit
        if self.channels==1:
            return cv.merge([self.img,self.img,self.img]) # greyscale
        elif self.channels==3:
            return self.img # just fine as it is
        else:
            # well, now we have something weird. If there are fewer than three, there must 
            # be two - use red and blue. If there are more than three, just use the first three.
            chans = cv.split(self.img)
            if self.channels==2:
                blk = np.zeros(self.img.shape[0:2]).astype(np.ubyte)
                return cv.merge([chans[0],blk,chans[1]])
            else:
                return cv.merge(chans[0:3])
            
            
    # extract the "subimage" - the image cropped to regions of interest,
    # with a mask for those ROIs
    def subimage(self):
        return SubImageROI(self)
        
    def __str__(self):        
        return "<Image {}x{} array:{} channels:{}, {} bytes>".format(self.w,self.h,
            str(self.img.shape),self.channels,self.img.nbytes)

    def copy(self):
        i = Image(self.img.copy())
        i.rois = [x for x in self.rois]
        return i

    # return a copy of the image, with the given spliced in at the
    # subimage's coordinates.
    def modifyWithSub(self,subimage,newimg):
        i = self.copy()
        x,y,w,h = subimage.bb
        i.img[y:y+h,x:x+w][subimage.mask]=newimg[subimage.mask]
        return i
