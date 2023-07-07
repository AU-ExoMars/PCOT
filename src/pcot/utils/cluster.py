# hierarchical clustering. 
# There are two versions here:
# hcluster is the algorithm performed by OpenCV itself as part of
# the calibration target code, but isn't public in pyqt so I've rewritten it.
# It works most of the time, but is only here for reference.
# However, I'm actually using scikit's clustering, as skcluster.
# The interface to this is via the cluster() function.

import cv2 as cv
import numpy as np
from random import randrange
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster


# takes a list of points and the number of points we expect in our cluster.
# Does hierarchical clustering, cutting until we get the right number of points.
# Unfortunately it doesn't always generate the correct number of points, so use skcluster below.
# From the OpenCV source: https://github.com/opencv/opencv/blob/master/modules/calib3d/src/circlesgrid.cpp

def hcluster(points, pn):
    if pn >= len(points):
        # not actually enough points to bother with
        return points

    n = len(points)

    # create a new nxn matrix of zeroes for the distances
    # also create initial clusters - we're using agglomerative clustering, so each item starts
    # in a cluster by itself
    dists = np.zeros((n, n), np.float32)
    distsMask = np.zeros((n, n), np.ubyte)
    clusters = [[] for i in range(0, n)]
    for i in range(0, n):
        clusters[i].append(i)
        for j in range(i + 1, n):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            dists[i, j] = cv.norm((dx, dy))
            distsMask[i, j] = 255
            dists[j, i] = dists[i, j]
            distsMask[j, i] = 255
    # and this does the clustering. It's magic.
    patternClusterIdx = 0
    while len(clusters[patternClusterIdx]) < pn:
        minval, maxval, minloc, maxloc = cv.minMaxLoc(dists, distsMask)
        minIdx = min(minloc[0], minloc[1])
        maxIdx = max(minloc[0], minloc[1])
        distsMask[maxIdx] = 0
        distsMask[:, maxIdx] = 0
        tmpRow = cv.min(dists[minloc[0]], dists[minloc[1]])
        dists[:, minIdx] = tmpRow.T

        clusters[minIdx].extend(clusters[maxIdx])
        patternClusterIdx = minIdx

    # largest cluster can have more than pn points; the original code just returns
    # here so I'll return None. This will happen if there's no way of separating out
    # a cluster?

    #    if len(clusters[patternClusterIdx])!=pn:
    #       return None

    # return point indices
    return clusters[patternClusterIdx]


def cluster(points, pn):
    """
    Input is a list of discovered ellipses as tuples (x,y,size)
    Output is a list of pn ellipses of the same type, indicating centroids of pn clusters.
    """
    if len(points) <= pn:  # degenerate case!
        return points

    # generate an array of just the centre positions
    centrePoints = np.array(points)
    # generate the linkage data
    Z = linkage(centrePoints, 'centroid')
    # find pn clusters in that array. Return value is a 1D array - k[i] is the cluster index to which point i
    # belongs; they appear to be 1-based.
    k = fcluster(Z, pn, criterion='maxclust')
    # now find the centroids
    lens = {}
    centroids = {}
    dim = centrePoints[0].shape
    for idx, clusterIdx in enumerate(k):
        centroids.setdefault(clusterIdx,np.zeros(dim)) # if not present, sets value
        centroids[clusterIdx] += points[idx]    # note that we are combining the full point data including size
        lens.setdefault(clusterIdx, 0)
        lens[clusterIdx] += 1
    for clusterIdx in centroids:
        centroids[clusterIdx] /= lens[clusterIdx]
    # turn that back into a list
    return centroids.values()
