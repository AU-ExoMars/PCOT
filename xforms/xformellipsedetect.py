import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
import utils.cluster

from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

@xformtype
class XformEllipseDetect(XFormType):
    """PANCAM target detection, work in progress."""
    def __init__(self):
        super().__init__("ellipsedetect","0.0.0")
        self.addInputConnector("","imggrey")
        self.addOutputConnector("img","img")
        self.addOutputConnector("data","ellipse")
        
    def createTab(self,n):
        return TabImage(n)

    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])
        
    def init(self,node):
        node.img = None
        node.data = None

    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        else:
            i,node.data = ellipseDetect(img.img)
            node.img = Image(i)
        node.setOutput(0,node.img)
        node.setOutput(1,node.data)

def ellipseDetect(img):
    params = cv.SimpleBlobDetector_Params()

    area = img.shape[0]*img.shape[1]
    
    minArea = area*0.000125
    maxArea = area*0.002
    print(area,minArea,maxArea)
      
    bestcount = 0
    
    # use varying maximum threshold, keep the largest number
    # of blobs found (if it's less than 8)
    
    for maxthresh in range(20,225,10):
        ui.mainui.msg("Threshold {}".format(maxthresh))
        params.thresholdStep = 10.0
        params.minThreshold = 10
        params.maxThreshold = maxthresh #220.0
 
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
        params.minDistBetweenBlobs= 10.0

        detector = cv.SimpleBlobDetector_create(params)
        keypoints = detector.detect(img)
        
        keypoints = utils.cluster.cluster(keypoints,5)
        if keypoints is not None:
            count = len(keypoints)
            for p in keypoints:
                print(p.pt,p.size)
            if count<=8 and count>bestcount:
                bestcount=count
                bestpoints=keypoints
        
    if bestcount>0:
        keypoints=bestpoints        
        print(keypoints)
        img = cv.drawKeypoints(img, keypoints, 
                None, (255, 0, 0), 
                cv.DrawMatchesFlags_DRAW_RICH_KEYPOINTS )
        ui.mainui.msg("done, {} ellipses found".format(len(keypoints)))
    else:
        keypoints=list()
        ui.mainui.msg("done, no ellipses found")
    return (img,keypoints)

