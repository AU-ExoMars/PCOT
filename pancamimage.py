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
            
        else:
            self.img = img.img
            self.bb = (0,0,img.w,img.h) # whole image
            self.mask = np.full((img.h,img.w),True) # full mask


# an image - just a numpy image and a list of ROI objects
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
            
    # extract the "subimage" - the image cropped to regions of interest,
    # with a mask for those ROIs
    def subimage(self):
        return SubImageROI(self)
        
    def __str__(self):        
        return "<Image {}x{} array:{} channels:{}>".format(self.w,self.h,
            str(self.img.shape),self.channels)

    def copy(self):
        i = Image(self.img.copy())
        i.rois = [x for x in self.rois]
        return i

    # return a copy of the image, with the given spliced in at the
    # subimage's coordinates.
    def modifyWithSub(self,subimage,newimg):
        i = self.copy()
        x,y,w,h = subimage.bb
        i.img[y:y+h,x:x+w]=newimg
        return i
