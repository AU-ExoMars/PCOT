import numpy as np

from pcot.datum import Datum
from pcot.sources import MultiBandSource, SourceSet
from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabimage import TabImage

from functools import reduce


@xformtype
class XformDecorr(XFormType):
    """Perform a decorrelation stretch on an RGB image"""

    def __init__(self):
        super().__init__("decorr stretch", "processing", "0.0.0")
        self.addInputConnector("rgb", Datum.IMG)
        self.addOutputConnector("rgb", Datum.IMG)
        self.hasEnable = True

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            out = None
        elif not node.enabled:
            out = img
        elif img.channels != 3:
            raise XFormException("DATA", "can only decorr stretch images with 3 channels")
        else:
            subimage = img.subimage()
            newimg = decorrstretch(subimage.img, subimage.mask)
            # in this case, all channels just come from the union of the sources
            sources = SourceSet(img.sources.getSources())
            out = img.modifyWithSub(subimage, newimg, sources=MultiBandSource([sources, sources, sources]))

        if out is not None:
            out.setMapping(node.mapping)

        node.out = Datum(Datum.IMG, out)
        node.setOutput(0, node.out)


def decorrstretch(A, mask):
    """
    Apply decorrelation stretch to image

    Arguments:
    A   -- image in cv2/numpy.array format
    mask -- mask, pixels to be manipulated are True (unlike usual numpy setting)
    """

    # save the original shape and image
    orig = A
    orig_shape = A.shape

    # reshape the image
    #         B G R
    # pixel 1 .
    # pixel 2   .
    #  . . .      .
    A = A.reshape((-1, 3)).astype(np.float64)
    # build a mask the same shape as the data
    mask = mask.flatten()
    mask = np.repeat(mask, 3).reshape(-1, 3)
    # apply the mask
    maskedA = np.ma.masked_array(data=A.copy(), mask=~mask)
    # covariance matrix of A (only those pixels in the mask)
    tt = np.ma.transpose(maskedA)
    cov = np.ma.cov(tt)
    # source and target sigma
    sigma = np.diag(np.sqrt(cov.diagonal()))
    # eigen decomposition of covariance matrix
    eigval, V = np.linalg.eig(cov)
    # fail if an eigenvalue is too small (monochrome image?)
    if min(abs(eigval)) < 0.00001:
        raise XFormException("DATA", "Eigenvalue too small for decorrelation stretch")
    # stretch matrix
    S = np.diag(1 / np.sqrt(eigval))
    # compute mean of each color in the masked area
    mean = np.ma.mean(maskedA, axis=0)
    # substract the mean from image
    maskedA -= mean
    # compute the transformation matrix
    T = reduce(np.dot, [sigma, V, S, V.T])
    # compute offset 
    offset = mean - np.dot(mean, T)
    # transform the image
    maskedA = np.dot(maskedA, T)
    # add the mean and offset
    maskedA += mean + offset
    # restore original shape
    B = maskedA.reshape(orig_shape)
    # for each color...
    for b in range(3):
        # ...normalize
        B[:, :, b] = (B[:, :, b] - B[:, :, b].min()) / (B[:, :, b].max() - B[:, :, b].min())
    # do any required conversion here
    B = B.astype(np.float32)
    # paste masked area into original subimage, we do this with flattened version
    # of the images to match the flat mask we made.
    orig = orig.flatten()
    B = B.flatten()
    np.putmask(orig, mask, B)
    return orig.reshape(orig_shape)
