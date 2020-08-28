import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
import utils.cluster

from xform import singleton,XFormType
from xforms.tabimage import TabImage


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
    else:
        keypoints=list()
        print("No ellipses found")
    return (img,keypoints)

@singleton
class XformEllipse(XFormType):
    def __init__(self):
        super().__init__("ellipse")
        self.addInputConnector("","imggrey")
        self.addOutputConnector("img","img")
        self.addOutputConnector("data","ellipse")
        
    def createTab(self,mainui,n):
        return TabImage(mainui,n)

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
            node.img,node.data = ellipseDetect(img)
        node.setOutput(0,node.img)
        node.setOutput(1,node.data)
