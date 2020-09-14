import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

# perform equalisation with a mask. Unfortunately cv.equalizeHist doesn't
# support masks.
# Takes a single-channel numpy array of ubyte
# and a single-channel mask of booleans

def equalize(img,mask):
    mask = mask.astype(np.ubyte)
    # algorithm source: https://docs.opencv.org/master/d5/daf/tutorial_py_histogram_equalization.html
    # get histogram; 256 bins of 0-256. Set the weight of all unmasked
    # pixels to zero so they don't get counted.
    print(img.shape)
    print(mask.shape)
    hist,bins = np.histogram(img,256,[0,256],weights=mask)
    # work out the cumulative dist. function and normalize it
    cdf = hist.cumsum()
    cdf_normalized = cdf * float(hist.max()) / cdf.max()
    # get a masked array, omitting zeroes, and use it to construct
    # a lookup table for old to new intensities
    cdf_m = np.ma.masked_equal(cdf,0)
    cdf_m = (cdf_m - cdf_m.min())*255/(cdf_m.max()-cdf_m.min())
    cdf = np.ma.filled(cdf_m,0).astype(np.ubyte)
    # and apply it to the masked region of the image
    np.putmask(img,mask,cdf[img])
    

@xformtype
class XformHistEqual(XFormType):
    def __init__(self):
        super().__init__("histequal","0.0.0")
        self.addInputConnector("","img")
        self.addOutputConnector("","img")
        
    def createTab(self,n):
        return TabImage(n)

    def generateOutputTypes(self,node):
        # output type 0 should be the same as input type 0, so a greyscale makes a
        # greyscale and an RGB makes an RGB..
        node.matchOutputsToInputs([(0,0)])
        
    def init(self,node):
        node.img = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            # can't equalize a non-existent image!
            node.img = None
        else:
            # first extract the ROI subimage; the rectangle which
            # contains the ROIS and a mask we should work on
            subimage = img.subimage()
            
            # now we need to perform equalisation on just the pixels
            # in the mask! For this operation it's a bit hairy, because
            # the nice OpenCV equalizeHist function doesn't do masks.
            # So the equalize() function above does that.
            
            # deal with 3-channel and 1-channel images
            if img.channels==3:
                r,g,b = cv.split(subimage.img)
                equalize(r,subimage.mask)
                equalize(g,subimage.mask)
                equalize(b,subimage.mask)
                equalized = cv.merge((r,g,b))
            else:
                equalized = cv.equalizeHist(subimage.img,subimage.mask)
            # make a copy of the image and paste the modified version of the subimage into it
            node.img = img.modifyWithSub(subimage,equalized)
        node.setOutput(0,node.img)
