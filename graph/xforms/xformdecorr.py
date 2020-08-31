from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType

from functools import reduce

class TabDecorr(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabcontrast.ui') # same UI as contrast
        self.w.dial.valueChanged.connect(self.setContrast)

        # sync tab with node
        self.onNodeChanged()

    def setContrast(self,v):
        # when a control changes, update node and perform
        self.node.tol = v/200
        self.node.perform()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.dial.setValue(self.node.tol*200)        
        self.w.canvas.display(self.node.img)

def decorrstretch(A, tol=None):
    """
    Apply decorrelation stretch to image

    Arguments:
    A   -- image in cv2/numpy.array format
    tol -- upper and lower limit of contrast stretching (0-0.5)
    """

    # save the original shape and image
    orig = A
    orig_shape = A.shape
    # reshape the image
    #         B G R
    # pixel 1 .
    # pixel 2   .
    #  . . .      .
    A = A.reshape((-1,3)).astype(np.float)
    # covariance matrix of A
    cov = np.cov(A.T)
    # source and target sigma
    sigma = np.diag(np.sqrt(cov.diagonal()))
    # eigen decomposition of covariance matrix
    eigval, V = np.linalg.eig(cov)
    # fail if an eigenvalue is too small (monochrome image?)
    if min(abs(eigval))<0.00001:
        return orig
    # stretch matrix
    S = np.diag(1/np.sqrt(eigval))
    # compute mean of each color
    mean = np.mean(A, axis=0)
    # substract the mean from image
    A -= mean
    # compute the transformation matrix
    T = reduce(np.dot, [sigma, V, S, V.T])
    # compute offset 
    offset = mean - np.dot(mean, T)
    # transform the image
    A = np.dot(A, T)
    # add the mean and offset
    A += mean + offset
    # restore original shape
    B = A.reshape(orig_shape)
    # for each color...
    for b in range(3):
        # apply contrast stretching if requested
        if tol is not None and tol>0:
            # find lower and upper limit for contrast stretching
            low, high = np.percentile(B[:,:,b], 100*tol), np.percentile(B[:,:,b], 100-100*tol)
            B[B<low] = low
            B[B>high] = high
        # ...rescale the color values to 0..255
        B[:,:,b] = 255 * (B[:,:,b] - B[:,:,b].min())/(B[:,:,b].max() - B[:,:,b].min())
    # return it as uint8 (byte) image
    return B.astype(np.uint8)


@singleton
class XformDecorr(XFormType):
    def __init__(self):
        super().__init__("decorr stretch")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("rgb","img888")
        self.autoserialise=('tol',)
        
    def createTab(self,mainui,n):
        return TabDecorr(mainui,n)
        
    def init(self,node):
        node.img = None
        node.tol = 0

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            node.img = decorrstretch(img,node.tol)
        node.setOutput(0,node.img)
