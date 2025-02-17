from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.utils import image
from pcot.xform import xformtype, XFormType
import cv2 as cv
import numpy as np

from skimage.transform import warp
from skimage.registration import optical_flow_tvl1

from pcot.xforms.tabdata import TabData


@xformtype
class XFormAutoRegister(XFormType):
    # https://scikit-image.org/docs/dev/api/skimage.registration.html#skimage.registration.optical_flow_tvl1
    # https://scikit-image.org/docs/dev/auto_examples/registration/plot_opticalflow.html

    """
    Use the TV-L1 solver to find an optical flow field for transforming one image into another. Not generally advised, and very slow.
    The node will output a version of the 'moving' image, distorted to map onto the 'fixed' image.

    Propagates uncertainty of the moving image by distorting that of the source image, and propagates
    DQs using nearest neighbour."""

    def __init__(self):
        super().__init__("tvl1 autoreg", "processing", "0.0.0", hasEnable=True)
        self.params = TaggedDictType()  # no parameters
        self.addInputConnector("moving", Datum.IMG)
        self.addInputConnector("fixed", Datum.IMG)
        self.addOutputConnector("moved", Datum.IMG)

    def init(self, node):
        pass

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
                out = warp(movingImg.img, warpdata, mode='edge').astype(np.float32)
                unc = warp(movingImg.uncertainty, warpdata, mode='edge').astype(np.float32)
                dqs = warp(movingImg.dq, warpdata, mode='edge', order=0).astype(np.uint16)
            else:
                chans = image.imgsplit(movingImg.img)
                out = image.imgmerge([warp(x, warpdata, mode='edge').astype(np.float32) for x in chans])
                chans = image.imgsplit(movingImg.uncertainty)
                unc = image.imgmerge([warp(x, warpdata, mode='edge').astype(np.float32) for x in chans])
                chans = image.imgsplit(movingImg.dq)
                dqs = image.imgmerge([warp(x, warpdata, mode='edge', order=0, preserve_range=True).astype(np.uint16) for x in chans])

            out = ImageCube(out, node.mapping, movingImg.sources, uncertainty=unc, dq=dqs)
            out = Datum(Datum.IMG, out)

        node.setOutput(0, out)

    def createTab(self, n, w):
        return TabData(n, w)
