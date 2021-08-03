import cv2 as cv
import numpy as np
from cv2 import KeyPoint

import pcot.conntypes as conntypes
import pcot.ui as ui
import pcot.utils.cluster
from pcot.channelsource import REDINTERNALSOURCE, GREENINTERNALSOURCE, BLUEINTERNALSOURCE

from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabimage import TabImage
from pcot.pancamimage import ImageCube




@xformtype
class XformEllipseDetect(XFormType):
    """PANCAM target detection, work in progress."""

    def __init__(self):
        super().__init__("ellipsedetect", "calibration", "0.0.0")
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("img", conntypes.IMG)
        self.addOutputConnector("data", conntypes.ELLIPSE)

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None
        node.data = None

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is None:
            node.img = None
        else:
            keypoints = ellipseDetect(img)
            node.data = keypoints

            rgb = (img.rgb() * 255).astype(np.ubyte)
            # here we have to turn the (x,y,size) back into keypoints just for drawing
            i = cv.drawKeypoints(rgb, [KeyPoint(x, y, size) for x, y, size in keypoints],
                                 None, (255, 0, 0),
                                 cv.DrawMatchesFlags_DRAW_RICH_KEYPOINTS)
            i = i.astype(np.float32) / 255

            # Here, we're slapping RED all over a greyscale image so we don't really know what
            # the sources should be - I'm using the fake RGB setup.
            node.img = ImageCube(i, rgbMapping=node.mapping, sources=[{REDINTERNALSOURCE},
                                                                      {GREENINTERNALSOURCE},
                                                                      {BLUEINTERNALSOURCE}])
        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))
        node.setOutput(1, conntypes.Datum(conntypes.DATA, node.data))


def setParams(params, maxthresh, minArea, maxArea):
    params.thresholdStep = 10.0
    params.minThreshold = 10
    params.maxThreshold = maxthresh

    params.filterByArea = True
    params.minArea = minArea
    params.maxArea = maxArea

    params.filterByColor = False

    params.filterByCircularity = True
    params.minCircularity = 0.7

    params.filterByConvexity = True
    params.minConvexity = 0.8

    params.filterByInertia = True
    params.minInertiaRatio = 0.5

    params.minRepeatability = 2
    params.minDistBetweenBlobs = 10.0


def ellipseDetect(img):
    """Find a set of ellipses in a multispectral image.
    Process:
        split image into channels
        adaptively threshold each channel separately into binary images
        in each channel, detect blobs of a certain range in size
        accumulate results into a single list
        cluster detection on that list
    """

    # blob detect only works on 8-bit images
    chans = img.channels
    img = (img.img * 255.0).astype(np.ubyte)

    # split image into separate channels - we can only do one at a time
    # We also adaptively threshold each channel!
    chanimgs = []
    for i in range(chans):
        chanimg = img[:, :, i]
        # adaptive thresholding with a neighbourhood of 11 pixels.
        chanimg = cv.adaptiveThreshold(chanimg, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv.THRESH_BINARY, 11, 0)
        chanimgs.append(chanimg)

    # set up detector parameters and create it
    params = cv.SimpleBlobDetector_Params()
    area = img.shape[0] * img.shape[1]
    minArea = area * 0.000125
    maxArea = area * 0.002
    setParams(params, 100, minArea, maxArea)        # maxthreshold, and min and max area of ellipses
    detector = cv.SimpleBlobDetector_create(params)

    # blob detector only works on 8-bit
    # run through each channel detecting ellipses separately, adding all those ellipses together.
    # Dups eliminated by clustering.
    keypoints = []                                  # accumulate keypoints here
    for chanimg in chanimgs:                        # for each channel
        kpchan = detector.detect(chanimg)           # detect things
        if kpchan is not None:
            for p in kpchan:
                print(p.pt, p.size)
            keypoints += kpchan                     # add keypoints to list

    # convert keypoints to (x,y,size) tuples - easier to turn into centroids
    keypoints = [(x.pt[0], x.pt[1], x.size) for x in keypoints]
    # find 8 clusters inside the keypoints
    print("Clustering on ", len(keypoints))
    keypoints = pcot.utils.cluster.cluster(keypoints, 8)
    return keypoints
