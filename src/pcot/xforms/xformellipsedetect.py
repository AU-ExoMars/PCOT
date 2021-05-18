import cv2 as cv
import numpy as np

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
        self.addInputConnector("", "img")
        self.addOutputConnector("img", "img")
        self.addOutputConnector("data", "ellipse")

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
            img = img.img
            if img.channels != 1:
                raise XFormException('DATA', 'Ellipse detection must be on greyscale images')

            i, node.data = ellipseDetect(img.img)
            # Here, we're slapping RED all over a greyscale image so we don't really know what
            # the sources should be - I'm using the fake RGB setup.
            node.img = ImageCube(i, rgbMapping=node.mapping, sources=[{REDINTERNALSOURCE},
                                                                      {GREENINTERNALSOURCE},
                                                                      {BLUEINTERNALSOURCE}])
        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))
        node.setOutput(1, conntypes.Datum(conntypes.RECT, node.data))


def ellipseDetect(img):
    params = cv.SimpleBlobDetector_Params()

    area = img.shape[0] * img.shape[1]

    minArea = area * 0.000125
    maxArea = area * 0.002
    print(area, minArea, maxArea)

    bestcount = 0

    # blob detect only works on 8-bit images
    img = (img * 255.0).astype(np.ubyte)

    # use varying maximum threshold, keep the largest number
    # of blobs found (if it's less than 8)

    for maxthresh in range(20, 225, 10):
        ui.msg("Threshold {}".format(maxthresh))
        params.thresholdStep = 10.0
        params.minThreshold = 10
        params.maxThreshold = maxthresh  # 220.0

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

        detector = cv.SimpleBlobDetector_create(params)
        # blob detector only works on 8-bit
        keypoints = detector.detect(img)

        keypoints = pcot.utils.cluster.cluster(keypoints, 5)
        if keypoints is not None:
            count = len(keypoints)
            for p in keypoints:
                print(p.pt, p.size)
            if 8 >= count > bestcount:
                bestcount = count
                bestpoints = keypoints

    if bestcount > 0:
        keypoints = bestpoints
        print(keypoints)
        # this will expand the image to three channels
        img = cv.drawKeypoints(img, keypoints,
                               None, (255, 0, 0),
                               cv.DrawMatchesFlags_DRAW_RICH_KEYPOINTS)
        ui.msg("done, {} ellipses found".format(len(keypoints)))
    else:
        # ...so if it fails we had also better expand the image to three channels.
        img = cv.merge([img,img,img])
        keypoints = list()
        ui.msg("done, no ellipses found")

    img = (img.astype(np.float32)) / 255.0
    print("Output image shape ",img.shape)
    return (img, keypoints)
