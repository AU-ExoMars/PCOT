from functools import reduce

import numpy as np

from pcot.xform import XFormException


def decorrelation_stretch(A, mask, stretch_factor=1, clip_percent=5):
    #  Modified from here: https://github.com/lbrabec/decorrstretch and heaven knows where they got it from.

    """
    Perform a decorrelation stretch on an RGB image by applying a whitening transform
    with stretch.

    This works by
    * calculating the covariance matrix
    * calculating a transform to a space in which the diagonals of the covariance matrix are 1 and the
      other elements are minimised (i.e. the bands are decorrelated) - so this is a form of PCA
    * applying that transform
    * applying a stretch factor to increase those diagonal variances - the principal components
    * apply the inverse transform
    * restore original image scaling
    * fix up the image mean

    **Ignores DQ and uncertainty**

    We return the image, and also the stds of the original bands and the eigenvalues of the PCA.
    """

    # save the original shape and image
    orig = A
    orig_shape = A.shape

    # flatten the image from a HxWx3 array into an (H*W)x3 array
    A = A.reshape((-1, 3)).astype(np.float64)
    # build a mask the same shape as the data
    mask = mask.flatten()
    mask = np.repeat(mask, 3).reshape(-1, 3)
    # apply the mask
    maskedA = np.ma.masked_array(data=A.copy(), mask=~mask)
    # covariance matrix of A (only those pixels in the mask)
    tt = np.ma.transpose(maskedA)
    cov = np.ma.cov(tt)
    # get the stddev matrix - this is a square matrix whose diagonals are the stddevs of each colour band.
    # This code just gets a copy of cov with the elements not on the diagonal set to zero, and the other elements
    # (the variance of each band) square rooted (i.e. stddev).
    stddevs = np.sqrt(cov.diagonal()) # we return these
    sigma = np.diag(stddevs)
    # eigen decomposition of covariance matrix - get the eigenvalues and eigenvectors
    eigval, V = np.linalg.eig(cov)
    # fail if an eigenvalue is too small (monochrome image?)
#    if min(abs(eigval)) < 0.00001:
#        raise XFormException("DATA", "Eigenvalue too small for decorrelation stretch")
    # stretch matrix - each principal component has a variance equal to its eigenvalue. If we want to give each PC
    # a new variance k^2, we scale by k/sqrt(eigval).
    S = np.diag(stretch_factor / np.sqrt(eigval))
    # compute mean of each color in the masked area
    mean = np.ma.mean(maskedA, axis=0)
    # substract the mean from image
    maskedA -= mean
    # compute the transformation matrix - the whitening tranform is sigma*V*S*transpose(T).
    # First we rotate into PCA space, then we apply the scaling, then we rotate back, then we
    # restore the original per-band scaling.
    T = reduce(np.dot, [sigma, V, S, V.T])
    # compute offset
    offset = mean - np.dot(mean, T)
    # transform the image
    maskedA = np.dot(maskedA, T)
    # add the mean and offset
    maskedA += mean + offset

    # now do a MATLAB-style clipping of extreme values, to avoid being overwhelmed by outliers
    # First calculate the boundaries where we want to clip - the top and bottom N percent of the data
    valid = maskedA.compressed()    # get unmasked elements as a flat array; percentile doesn't work on masked arrays
    lo = np.percentile(valid, clip_percent)
    hi = np.percentile(valid, 100-clip_percent)
    # Normalise globally to that range
    maskedA = (maskedA-lo)/(hi-lo)
    # and clip the outliers, which will be outside.
    maskedA = np.clip(maskedA,0,1)

    # restore original shape
    B = maskedA.reshape(orig_shape)

    # do any required conversion here
    B = B.astype(np.float32)
    # paste masked area into original subimage, we do this with flattened version
    # of the images to match the flat mask we made.
    orig = orig.flatten()
    B = B.flatten()
    np.putmask(orig, mask, B)
    return orig.reshape(orig_shape), stddevs, eigval
