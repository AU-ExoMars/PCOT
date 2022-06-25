from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.utils import image
from pcot.xform import xformtype, XFormType
import cv2 as cv
import numpy as np

from skimage.transform import warp
from skimage.registration import optical_flow_tvl1

from pcot.xforms.tabimage import TabImage


@xformtype
class XFormAutoRegister(XFormType):
    # https://scikit-image.org/docs/dev/api/skimage.registration.html#skimage.registration.optical_flow_tvl1
    # https://scikit-image.org/docs/dev/auto_examples/registration/plot_opticalflow.html

    """
    Use the TV-L1 solver to find an optical flow field for transforming one image into another. Not generally advised, and very slow.
    The node will output a version of the 'moving' image, distorted to map onto the 'fixed' image."""

    def __init__(self):
        super().__init__("tvl1 autoreg", "processing", "0.0.0")
        self.addInputConnector("moving", Datum.IMG)
        self.addInputConnector("fixed", Datum.IMG)
        self.addOutputConnector("moved", Datum.IMG)

    def init(self, node):
        node.out = None

    def perform(self, node):
        # read images
        movingImg = node.getInput(0, Datum.IMG)
        fixedImg = node.getInput(1, Datum.IMG)

        if fixedImg is None or movingImg is None:
            out = None
        else:
            # convert to gray
            mat = np.array([1 / movingImg.channels] * movingImg.channels).reshape((1, movingImg.channels))
            moving = cv.transform(movingImg.img, mat)
            mat = np.array([1 / fixedImg.channels] * fixedImg.channels).reshape((1, fixedImg.channels))
            fixed = cv.transform(fixedImg.img, mat)

            # compute the optical flow
            v, u = optical_flow_tvl1(fixed, moving)

            nr, nc = moving.shape
            row_coords, col_coords = np.meshgrid(np.arange(nr), np.arange(nc), indexing='ij')

            warpdata = np.array([row_coords + v, col_coords + u])
            if movingImg.channels == 1:
                out = warp(movingImg.img, warpdata, mode='edge')
            else:
                chans = image.imgsplit(movingImg)
                outs = [warp(x, warpdata, mode='edge') for x in chans]
                out = image.imgmerge(outs)

            out = ImageCube(out, node.mapping, movingImg.sources)

        node.out = Datum(Datum.IMG, out)
        node.setOutput(0, node.out)

    def createTab(self, n, w):
        return TabImage(n, w)
