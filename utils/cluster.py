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

def hcluster(points,pn):
    if pn>=len(points):
        # not actually enough points to bother with
        return points
        
    n = len(points)

    # create a new nxn matrix of zeroes for the distances
    # also create initial clusters - we're using agglomerative clustering, so each item starts
    # in a cluster by itself
    dists = np.zeros((n,n),np.float)
    distsMask = np.zeros((n,n),np.ubyte)
    clusters = [[] for i in range(0,n)]
    for i in range(0,n):
        clusters[i].append(i)
        for j in range(i+1,n):
            dx = points[i][0]-points[j][0]
            dy = points[i][1]-points[j][1]
            dists[i,j]=cv.norm((dx,dy))
            distsMask[i,j]=255
            dists[j,i]=dists[i,j]
            distsMask[j,i]=255
    # and this does the clustering. It's magic.
    patternClusterIdx = 0
    while len(clusters[patternClusterIdx])<pn:
        minval,maxval,minloc,maxloc = cv.minMaxLoc(dists,distsMask)
        minIdx = min(minloc[0],minloc[1])
        maxIdx = max(minloc[0],minloc[1])
        distsMask[maxIdx] = 0
        distsMask[:,maxIdx] = 0
        tmpRow = cv.min(dists[minloc[0]],dists[minloc[1]])
        dists[:,minIdx]=tmpRow.T

        clusters[minIdx].extend(clusters[maxIdx])
        patternClusterIdx=minIdx
        
    # largest cluster can have more than pn points; the original code just returns
    # here so I'll return None. This will happen if there's no way of separating out
    # a cluster?
    
#    if len(clusters[patternClusterIdx])!=pn:
#       return None
    
    # return point indices
    return clusters[patternClusterIdx]
    

# now for scikit.

def skcluster(points,pn):
    points=np.array(points)
    Z = linkage(points,'ward')
    # we want to find a cluster with pn points in. Cut the dendrogram at successively
    # higher (more clusters) points until we get a cluster of the desired size. This
    # is a somewhat unorthodox method.
    for i in range(1,len(points)):
        # this gives an array of i clusters, except it's the cluster index for
        # each element. We want to find a cluster in here with n members. We need
        # to build an array of clusters. 
        k = fcluster(Z,i,criterion='maxclust')
        for j in range(1,max(k)+1):
            clust = np.nonzero(k==j)[0]
            if clust.size==pn:
                # just return the first cluster we find
                return clust.tolist()
            

def cluster(points,pn):
    if len(points)<=pn: # degenerate case!
        return points
    # takes a bunch of KeyPoints and return a cluster of pn of them.
    k = np.array([x.pt for x in points])
    idxs = skcluster(k,pn)
    # now use the indices for the cluster to index back into the keypoints
    if idxs is None:
        return None
    else:
        return [points[i] for i in idxs]
    
# test code
if __name__ == "__main__":
    for i in range(0,1000):
        list=[]
        for i in range(0,100):
            p = (randrange(0,100),randrange(0,100))
            list.append(p)
        print(hcluster(list,5),skcluster(list,5))
