from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas
from xform import xformtype, XFormType
from xforms.tabimage import TabImage
from pancamimage import ImageCube

from functools import reduce


@xformtype
class XformDecorr(XFormType):
    """Perform a decorrelation stretch on an RGB image"""

    def __init__(self):
        super().__init__("decorr stretch", "processing", "0.0.0")
        self.addInputConnector("rgb", "imgrgb")
        self.addOutputConnector("rgb", "imgrgb")
        self.hasEnable = True

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        elif not node.enabled:
            node.img = img
        elif img.channels != 3:
            ui.error("Can't decorr stretch images with other than 3 channels")
        else:
            subimage = img.subimage()
            newimg = decorrstretch(subimage.img, subimage.mask)
            node.img = img.modifyWithSub(subimage, newimg)
        if node.img is not None:
            node.img.setMapping(node.mapping)
        node.setOutput(0, node.img)


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
    origmask = mask

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
        ui.error("Eigenvalue too small for decorrelation stretch")
        return orig
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
