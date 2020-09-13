import numpy as np
import cv2 as cv

#
# Classes to encapsulate an image which can be any number of channels
# and also incorporates region-of-interest data.

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
    def mask(self,img):
        return None
        
# given an Image and list of ROIs, get the bounding box within the containing image as (x,y,w,h).
# If no list is given, use that built into the Image.
def getROIsBB(img,rois=None):
    if rois is None:
        rois = img.rois
    bbs = [r.bb() for r in rois] # get bbs
    x1 = min([b[0] for b in bbs])
    y1 = min([b[1] for b in bbs])
    x2 = max([b[0]+bb[2] for b in bbs])
    y2 = max([b[1]+bb[3] for b in bbs])
    return (x1,y1,x2-x1,y2-y1)
    
                    
# a rectangle ROI
        
class ROIRect(ROI):
    def __init__(self,x,y,w,h):
        self.x=x
        self.y=y
        self.w=w
        self.h=h
    def bb(self):
        return (self.x,self.y,self.w,self.h)
    def mask(self,img):
        # return a boolean array of True, same size as BB
        return np.full((self.h,self.w),True)

# an image - just a numpy image and an ROI
class Image:
    # create image from numpy array
    def __init__(self,img):
        self.img = img # the image numpy array
        # first, check the dtype is valid
        if self.img.dtype != np.ubyte:
            raise Exception("Images must be 8-bit")
        self.rois = []  # no ROI
        self.shape = img.shape
        # set the image type
        if len(img.shape)==2:
            # 2D image
            self.channels=1
        else:
            self.channels=img.shape[2]
            if self.channels!=3:
                raise Exception("Images must be greyscale or RGB")
        self.w = img.shape[1]
        self.h = img.shape[0]
        
    # get a numpy image (not another Image) we can display on an RGB surface
    def rgb(self):
        # assume we're 8 bit
        if self.channels==1:
            return cv.merge([self.img,self.img,self.img]) # greyscale
        elif self.channels==3:
            return self.img # just fine as it is
        else:
            raise Exception("cannot convert {} to RGB".format(self))
            
    # extract the bounding box of all ROIs
    def getROI(self):
        
    def __str__(self):        
        return "<Image {}x{} array:{} channels:{}>".format(self.w,self.h,
            str(self.img.shape),self.channels)

