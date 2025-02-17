"""
Author: Joseph Metcalfe

This node is designed as part of my major project to detect the centre coordinates of all patches
of the PCT on the ExoMars rover. It will take an image as an input and output a custom datumn
holding the patch identities and their coordinates for all detected patches.

"""
import math
from os import path

# assorted functional imports
import cv2 as cv
import numpy as np
# QT imports for interfacing with the front-end
from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QImage, QPixmap
from PySide2.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QMessageBox

from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.rois import ROICircle
from pcot.ui.tabs import Tab
from pcot.xform import xformtype, XFormType

# Set the default values for object detection parameters
# definitions of these parameters found in parameter description button on node
DP = 1.0
MINDISTANCE = 27.0
CANNYHIGHPARAM = 55.0
CANNYLOWPARAM = 24.0
MINRADIUS = 8
MAXRADIUS = 24


def createInterpolatedROI(x, y, r, label):
    """
    Create a new ROI object with the given coordinates and label
    """
    r = ROICircle(x, y, r, label=label)
    r.colour = (0, 1, 1)
    return r


def toPair(x):
    """
    If the input is not a coordinate pair (x,y) but an ROICircle, convert to pair.
    Ugly.
    """
    if isinstance(x, ROICircle):
        return x.x, x.y
    else:
        return x


# This class defines the back-end functionality of the node
# tag allows auto-registration of node
@xformtype
class XformPCTPatchDetection(XFormType):
    """
    A Node that takes in an image holding the ExoMars Rover PCT and outputs the centre coordinates
    in the image of each of the PCT patches.
    """

    def __init__(self):
        """
        Initialise the PCT patch detection node and create the input/output connectors
        """
        # constructor for XFormType, takes name, groupname and version
        super().__init__("PCT Patch Detection", "calibration", "1.0.0")
        # creates input to node of an image datum
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("img+rois", Datum.IMG)
        # set following node variables to be serialised when required, which is needed for saving and the undo stack
        self.autoserialise = ("parametersLocked",)  # this is kept as autoserialise but not a parameter

        # register parameters for the OpenCV HoughCircles detection
        # these should match the default values of the parameter sliders and be within slider limits
        self.params = TaggedDictType(
            dp=("Inverse ratio of the accumulator resolution to the image resolution for Hough detections", float, DP),
            minDist=("Minimum distance between the centers of the detected circles", float, MINDISTANCE),
            cannyHighParam=("Higher of the two Canny edge detection parameters", float, CANNYHIGHPARAM),
            cannyLowParam=("Lower of the two CAnny edge detection parameters", float, CANNYLOWPARAM),
            minRadius=("Minimum circle radius for patch detection (pixels)", int, MINRADIUS),
            maxRadius=("Maximum circle radius for patch detection (pixels)", int, MAXRADIUS),
        )

    def createTab(self, node, window):
        """
        Creates the graphical interface object for the PCT patch detection node
        """
        # hooks node onto it's front-end interface code
        return TabPCTPatchDetection(node, window)

    def init(self, node):
        """
        Initialise the node instance variables for the PCT patch detection node
        """
        # image that will be taken from input
        node.inputImg = None
        # the detections Datum
        node.detections = None

        # additionally create a variable to hold the state of the paramater lock checkbox
        # this needs to be held as a variable in the node to allow it to use the undo stack and saving
        node.parametersLocked = True

        # the subimage to show of detections made
        node.detectionsImage = None
        # and the coordinates to crop the image around the detections, format is [minX, maxX, minY, maxY]
        node.detectionExtremities = None

        # set of attributes to use once detections are made for patch identification
        node.detectionDistances = None
        node.averageDistanceToLargePatch = None

    def clearData(self, xform):
        xform.inputImg = None

    def perform(self, node):
        """
        Run the main functionality of the PCT patch detection node upon any changes to the node. This will take
        an image input and produce output that is None or the PCTDataType type.
        """

        # clear any existing output from the node
        node.clearOutputsAndTempData()      # not sure why Joseph is doing this, shouldn't be necessary.
        # get input from linked node if it exists - must be an image
        img = node.getInput(0, Datum.IMG)

        # reset the known detections
        node.detections = None
        node.detectionsImage = None
        node.detectionExtremities = None

        # if an image has been inputted:
        if img is not None:
            # set img for display, copy to avoid using image still owned by previous node
            node.inputImg = img.copy()
            node.inputImg.setMapping(node.mapping)

            # perform initial circle detection for patches
            circlesList, workingImg = self.detectCircles(node, looseDetectionsLevel=0)

            # if any detections were made:
            if circlesList is not None:

                # filter detections to just clustered centres to filter out any not on the PCT
                # two step filtering produces very good results even on high false positive images
                filteredCirclesList = self.filterDetections(self.filterDetections(circlesList))

                # calculate rough area of the image PCT exists in for use by loose detections or output plot
                self.getDetectionBoundaries(node, filteredCirclesList)

                # perform second stage looser search if not all patches detected first time
                if len(filteredCirclesList) < 8:
                    # perform search with lowered canny params on limited area
                    circlesList, _ = self.detectCircles(node, looseDetectionsLevel=1)
                    # and filter the detections by clusters again
                    filteredCirclesList = self.filterDetections(self.filterDetections(circlesList))

                    # if detections still below 8 loosen lower canny parameter slightly further
                    if len(filteredCirclesList) < 8:
                        # perform search with lowered canny params on limited area
                        circlesList, _ = self.detectCircles(node, looseDetectionsLevel=2)
                        # and filter the detections by clusters again
                        filteredCirclesList = self.filterDetections(self.filterDetections(circlesList))

                    # revert subimage detection coordinates to main image coordinates
                    for i in filteredCirclesList:
                        i[0] = i[0] + node.detectionExtremities[0]
                        i[1] = i[1] + node.detectionExtremities[2]
                    # re-calculate margins for output image in case of new detections
                    self.getDetectionBoundaries(node, filteredCirclesList)

                # at this point detections have been made, we can go to patch identification
                self.solvePatchDetections(node, filteredCirclesList)

                # now expand the filtered circle list an extra column to the second dimension - this will hold if the detection is
                # native or not, i.e. if it was detected by the detector or interpolated due to missing patch identities
                # with this extra column True = native detection and False = interpolated detection
                finalCirclesList = self.expandCirclesList(filteredCirclesList)

                # if not all PCT patches were identified, we need to try and derive the locations of missing patches
                # from the two large ones and any others
                if not node.detections.complete and None not in (node.detections.Pyroceram, node.detections.WCT2065):
                    # update the circles list with interpolated detections while also attempting to pair unidentified detections to patch identities
                    # recursions are capped based on how many patches could be missing and this function still predict all patches
                    finalCirclesList = self.interpolateMissingDetections(node, finalCirclesList, recursionsLeft=5)

                    # at this point if the interpolation still hasn't produced a complete set of detections, the solver can be attempted again
                    # with any new detections predicted by the interpolator - this is the final shot at solving the patch identities
                    if not node.detections.complete:
                        self.solvePatchDetections(node, finalCirclesList)

                # now try to detect flippage and modify the detections if required
                self.detectFlippage(node)
                node.detections.labelROIs()

                # create image showing patch detections and identities to the user
                self.plotDetections(node, finalCirclesList, workingImg)
                # set the ROIs on the input image (which is a copy of the actual input) - this
                # replaces any ROIs already there!
                roisList = node.detections.toROIList()
                node.inputImg.rois = [x for x in roisList if x is not None]
                # and that will be the output image
                node.setOutput(0, Datum(Datum.IMG, node.inputImg, node.inputImg.sources))
            else:
                # if no circles found
                node.detections = "No detections made, try altering detection parameters."
                node.detectionsImage = None

                # set node output to None:
                node.setOutput(0, Datum.null)

        # if no image inputted:
        else:
            node.img = None

            # set node output to None:
            node.setOutput(0, None)

    def detectCircles(self, node, looseDetectionsLevel):
        """
        Perform OpenCV's HoughCircle detection to detect pct patches in images
        """
        # create 1 channel image with averaged values from each image channel to achieve greyscale effect.
        # We don't need to do that if it's a single channel image already - they are stored as 2D.

        if node.inputImg.channels > 1:
            workingImg = np.mean(node.inputImg.img, axis=(2))
        else:
            workingImg = node.inputImg.img

        # convert working image to uint8 type required by HoughCircles method
        workingImg = cv.normalize(workingImg, None, 0, 255, cv.NORM_MINMAX, cv.CV_8U)

        # if using loose detections on just the PCT area in a re-run crop the image to just the PCT
        if looseDetectionsLevel != 0:
            workingImg = workingImg[node.detectionExtremities[2]:node.detectionExtremities[3],
                         node.detectionExtremities[0]:node.detectionExtremities[1]]
            # additionally, cache some parameters that will be later changed
            cachedParam1 = node.params.cannyHighParam
            cachedParam2 = node.params.cannyLowParam
            # and alter the parameters temporarily for looser detections, limiting by slider minimums
            node.params.cannyHighParam = max(node.params.cannyHighParam - 32, 20)
            # two levels of looser detections depending on current detection state
            if looseDetectionsLevel == 1:
                node.params.cannyLowParam = max(node.params.cannyLowParam - 5, 10)
            elif looseDetectionsLevel == 2:
                node.params.cannyLowParam = max(node.params.cannyLowParam - 8, 10)

        # apply large kernel low blurs to smooth large sections like sand
        blurredWorkingImg = cv.GaussianBlur(workingImg, (17, 17), 1.5)
        # then moderate but local gaussian blur to smooth smaller sections
        blurredWorkingImg = cv.GaussianBlur(blurredWorkingImg, (3, 3), 3.5)

        # derive a list of detected circles in the image
        # details of what each parameter does can be found here:
        # https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html#ga47849c3be0d0406ad3ca45db65a25d2d
        circlesList = cv.HoughCircles(blurredWorkingImg,
                                      cv.HOUGH_GRADIENT,
                                      dp=node.params.dp,
                                      minDist=node.params.minDist,
                                      param1=node.params.cannyHighParam,
                                      param2=node.params.cannyLowParam,
                                      minRadius=node.params.minRadius,
                                      maxRadius=node.params.maxRadius)

        # post-processing if detections were loose on just PCT area:
        if looseDetectionsLevel != 0:
            # reset parameters to cached versions as they were changed
            node.params.cannyHighParam = cachedParam1
            node.params.cannyLowParam = cachedParam2
            # and index the detection coordinates to the original image

        if circlesList is not None:
            # convert raw floats to rounded numbers then to unsigned long to allow use as coordinates
            circlesList = np.uint16(np.around(circlesList))
            return circlesList[0], workingImg
        else:
            # returning None for circlesList if no detections made to make error pickup easier
            return None, workingImg

    def filterDetections(self, circlesList):
        """
        Filter circle detections by distance to other detections to reduce false positives
        """
        # first work out the average euclidan distance between every detection
        # create variable to stack distances in then divide itself to a mean
        overallAvgEuclidan = 0.0
        # go through every combination of detections
        for detection in circlesList:
            for comparisonDetection in circlesList:
                # filter out identical coordinates
                if (detection[0], detection[1]) != (comparisonDetection[0], comparisonDetection[1]):
                    # calculate euclidian distance and add it to total
                    overallAvgEuclidan += math.dist((comparisonDetection[0], comparisonDetection[1]),
                                                    (detection[0], detection[1]))
        # average based on how many unique pairs of coordinates there will be - avoiding dividing by 0 on 1 detection
        overallAvgEuclidan = overallAvgEuclidan / max((len(circlesList) * len(circlesList) - len(circlesList)), 1)

        # create empty list to start building filtered list in
        filteredCirclesList = []

        # now go through list of detections to filter to just those with an avg dist to other detections lower than overall avg dist to other detections
        for detection in circlesList:
            averageDistanceToOtherDetections = 0
            for comparisonDetection in circlesList:
                # filter out identical coordinates
                if (detection[0], detection[1]) != (comparisonDetection[0], comparisonDetection[1]):
                    averageDistanceToOtherDetections += math.dist((comparisonDetection[0], comparisonDetection[1]),
                                                                  (detection[0], detection[1]))
            averageDistanceToOtherDetections = averageDistanceToOtherDetections / len(circlesList) - 1

            # filter with some margin to avoid affecting performance with no false positives
            if averageDistanceToOtherDetections < overallAvgEuclidan * 1.1:
                filteredCirclesList.append([detection[0], detection[1], detection[2]])

        return filteredCirclesList

    def getDetectionBoundaries(self, node, filteredCirclesList):
        """
        Calculate the section of the image that filtered detections exist within
        """
        if filteredCirclesList is not None and filteredCirclesList != []:
            # get extremity centre points expanded by a margin to determine which section of image to plot
            # init variables in a way that couldn't be a valid coordinate
            minX, maxX, minY, maxY = -1, -1, -1, -1
            # first set the limits to the extremity centre points themselves
            for i in filteredCirclesList:
                if i[0] < minX or minX == -1:
                    minX = max(i[0], 0)
                if i[0] > maxX or maxX == -1:
                    maxX = min(i[0], node.inputImg.w)
                if i[1] < minY or minY == -1:
                    minY = max(i[1], 0)
                if i[1] > maxY or maxY == -1:
                    maxY = min(i[1], node.inputImg.h)

            # add margin of twice the max detected radius around the points
            maxDetectedRadius = max(detection[2] for detection in filteredCirclesList)
            minX = max(minX - maxDetectedRadius * 2, 0)
            maxX = min(maxX + maxDetectedRadius * 2, node.inputImg.w)
            minY = max(minY - maxDetectedRadius * 2, 0)
            maxY = min(maxY + maxDetectedRadius * 2, node.inputImg.h)

            # set these margins to a node variable to cut the image to just the PCT for loose detection if needed
            node.detectionExtremities = [minX, maxX, minY, maxY]
        else:
            node.detectionExtremities = None

    def plotDetections(self, node, filteredCirclesList, workingImg):
        """
        Create an output image with patch detections and annotations plotted onto it
        """
        # create a canvas to draw annotations for the detections plot on
        plotCanvas = cv.cvtColor(workingImg.copy(), cv.COLOR_GRAY2BGR)

        # draw annotations of all detections onto plotting canvas
        for circle in filteredCirclesList:
            # draw a green outer circle if it is a native detection
            if circle[3]:
                cv.circle(plotCanvas, (int(circle[0]), int(circle[1])), int(circle[2]), (0, 255, 0), 1)
            # draw a blue multi-step circle if it is interpolated
            # this distinction is important for colour blind users, and opencv has nothing better
            # such as dashed lines or filling a shape with hashing that doesnt take lots of code
            else:
                cv.circle(plotCanvas, (int(circle[0]), int(circle[1])), int(circle[2]), (255, 0, 0), 1)
                cv.circle(plotCanvas, (int(circle[0]), int(circle[1])), int(circle[2] / 1.33), (255, 0, 0), 1)
                cv.circle(plotCanvas, (int(circle[0]), int(circle[1])), int(circle[2] / 2), (255, 0, 0), 1)
                cv.circle(plotCanvas, (int(circle[0]), int(circle[1])), int(circle[2] / 4), (255, 0, 0), 1)

        # write all patch identities that were derived in their respective circles
        # create arrays to allow doing this in a loop
        patchIdentities = [node.detections.NG4, node.detections.RG610, node.detections.BG3,
                           node.detections.NG11, node.detections.OG515, node.detections.BG18,
                           node.detections.Pyroceram, node.detections.WCT2065]
        patchNames = ["NG4", "RG610", "BG3", "NG11", "OG515", "BG18", "Pyroceram", "WCT2065"]
        namePostionAdjustments = [[-10, +4], [-18, +4], [-10, +4], [-13, +4], [-18, +4], [-13, +4], [-30, +4],
                                  [-24, +4]]

        # loop through the identities, writing the name if the detection isnt null
        for patchIdentity in range(0, 8):
            p = patchIdentities[patchIdentity]
            if p is not None:
                cv.putText(plotCanvas, patchNames[patchIdentity],
                           (p.x + namePostionAdjustments[patchIdentity][0],
                            p.y + namePostionAdjustments[patchIdentity][1]),
                           cv.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1, 2)

        # add a pixel scale to the bottom corner of the image
        # caclulate coordinates to draw the scale from, it will be the bottom left of the scale with a margin
        scaleAnchorCoordinates = [node.detectionExtremities[0] + 5, node.detectionExtremities[3] - 5]
        # draw the text element of the scale
        cv.putText(plotCanvas, "50px",
                   (scaleAnchorCoordinates[0] + 15, scaleAnchorCoordinates[1] - 4),
                   cv.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1, 2)
        # draw lines to make the scale
        cv.line(plotCanvas, (scaleAnchorCoordinates[0], scaleAnchorCoordinates[1]),
                (scaleAnchorCoordinates[0], scaleAnchorCoordinates[1] - 6), (0, 0, 255), 1)
        cv.line(plotCanvas, (scaleAnchorCoordinates[0], scaleAnchorCoordinates[1]),
                (scaleAnchorCoordinates[0] + 50, scaleAnchorCoordinates[1]), (0, 0, 255), 1)
        cv.line(plotCanvas, (scaleAnchorCoordinates[0] + 50, scaleAnchorCoordinates[1]),
                (scaleAnchorCoordinates[0] + 50, scaleAnchorCoordinates[1] - 6), (0, 0, 255), 1)

        # make subimage from the full plot canvas and display that - RGB as it will be given to a QImage
        node.detectionsImage = cv.cvtColor(plotCanvas[node.detectionExtremities[2]:node.detectionExtremities[3],
                                           node.detectionExtremities[0]:node.detectionExtremities[1]].copy(),
                                           cv.COLOR_BGR2RGB)

    def expandCirclesList(self, inputCirclesList):
        """
        Add a column to a circle detections list to allow marking detections as original or interpolated
        """
        if inputCirclesList is not None and inputCirclesList != []:
            # create an empty list to fill
            expandedList = []
            # for each circle copy the elements, plus the new field
            for circle in inputCirclesList:
                # here, each element of the new column is marked as True, indicating a native detection.
                # This is becase this function should only run before interpolation is attempted
                expandedList.append([
                    circle[0],
                    circle[1],
                    circle[2],
                    True
                ])
            return (expandedList)
        return None

    def solvePatchDetections(self, node, detections):
        """
        Determine patch identities through a method of eliminating identity possibilities for each detection
        """
        # create a data structure to represent the identity possibilities of each patch
        # First dimension represents detections (i.e. patchIdentityPossibilities[0][] is the first detection in the array)
        # Second dimension represents identity possibilities (i.e. patchIdentityPossibilities[][0] is the first identity possibility)
        # Identities are indexed as: NG4, RG610, BG3, NG11, OG515, BG18, Pyroceram, WCT2065
        # Identities are handled as True/1 = Possible Identity and False/0 = Impossible Identity
        patchIdentityPossibilities = np.ones((len(detections), 8), np.int8)

        # sort detections by radius descending to make solving easier
        detections = sorted(detections, key=lambda detection: detection[2], reverse=True)

        # if more than 1 detection was made, we can identify attributes to help solve detection identities then apply rules to solve them
        # this condition exists as all rules rely on comparing multiple detections
        if len(detections) > 1:
            # create a set of attributes that can be used by the solver to help determine identities
            # start with an array holding the distance from each detection to each other detection
            node.detectionDistances = np.zeros((len(detections), len(detections)), float)
            for i in range(0, len(detections)):
                for j in range(0, len(detections)):
                    node.detectionDistances[i][j] = math.dist((detections[j][0], detections[j][1]),
                                                              (detections[i][0], detections[i][1]))

            # then measure the mean distance from a detection to Pyroceram and WCT-2065 (known as largest two detections)
            node.averageDistanceToLargePatch = 0
            for i in range(0, len(detections)):
                node.averageDistanceToLargePatch += np.mean(
                    [node.detectionDistances[i][0], node.detectionDistances[i][1]])
            node.averageDistanceToLargePatch = node.averageDistanceToLargePatch / 6

            # peform a recursive rule application, capped at a reasonable recursion depth
            patchIdentityPossibilities = self.identitySolve(node, detections, patchIdentityPossibilities, 0)

        # check the identity possibility array to get the index in the detections array of each patch
        # first create a dictionary of the signatures each patch will match in the detection array
        patchSignatures = {
            'NG4': [1, 0, 0, 0, 0, 0, 0, 0],
            'RG610': [0, 1, 0, 0, 0, 0, 0, 0],
            'BG3': [0, 0, 1, 0, 0, 0, 0, 0],
            'NG11': [0, 0, 0, 1, 0, 0, 0, 0],
            'OG515': [0, 0, 0, 0, 1, 0, 0, 0],
            'BG18': [0, 0, 0, 0, 0, 1, 0, 0],
            'Pyroceram': [0, 0, 0, 0, 0, 0, 1, 0],
            'WCT2065': [0, 0, 0, 0, 0, 0, 0, 1]
        }

        # create another dictionary that will hold coordinates or 'None' for found/not found patches
        # this has to be a dictionary to allow coordinates to be referenced by patch identity
        patches_found = {}

        # loop through the dictionary keys and values, looking for matching values and using the associated key as the patch name if found
        for patch_name, patch_signature in patchSignatures.items():
            try:
                # convert the match into an index in the patchIdentityPossibilities array of that matching signature
                patch_index = np.where((patchIdentityPossibilities == patch_signature).all(axis=1))[0][0]
                # use the index in the detections array to fetch the matching x and y coordinates
                patches_found[patch_name] = detections[patch_index].copy()
            except:
                # if no matching signature is found, the detection that matched the patch wasnt identified, so put in a null value instead of coordinates
                patches_found[patch_name] = None

        # create a PCT patch identity datumn to become the node output, inserting in the coordinates or 'None' values 
        patchIdentities = PCTPatchData(patches_found.get('NG4'), patches_found.get('RG610'),
                                       patches_found.get('BG3'), patches_found.get('NG11'),
                                       patches_found.get('OG515'), patches_found.get('BG18'),
                                       patches_found.get('Pyroceram'), patches_found.get('WCT2065'))

        # output the detections to the node variable that links to the text display and 
        node.detections = patchIdentities

    def identitySolve(self, node, detections, patchIdentityPossibilities, recursionDepth):
        """
        Restrained recursive function to apply rules about patch identities to detections
        """

        # go through every detection made to see if any rules apply to them
        for currentDetectionIndex in range(0, len(detections)):

            # skip all checks on a detection if it's identity is already certain
            if patchIdentityPossibilities[currentDetectionIndex].sum() > 1:

                # Rule 1: A detection that is one of the two largest must be one of Pyroceram or WCT-2065
                if currentDetectionIndex <= 1:
                    # Reduce identities to just two biggest patches
                    patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 0, 0, 0, 0, 1, 1]

                    # Rule 2: If two biggest patches are identified, the one with highest Y coordinate must be Pyroceram and lowest must be WCT-2065
                    if np.array_equal(patchIdentityPossibilities[0], [0, 0, 0, 0, 0, 0, 1, 1]) and np.array_equal(
                            patchIdentityPossibilities[1], [0, 0, 0, 0, 0, 0, 1, 1]):
                        if detections[0][1] < detections[1][1]:
                            # first detection has smaller Y coordinate, this must be WCT-2065 and index 1 must be Pyroceram
                            patchIdentityPossibilities[1] = [0, 0, 0, 0, 0, 0, 1, 0]
                            patchIdentityPossibilities[0] = [0, 0, 0, 0, 0, 0, 0, 1]
                        else:
                            # first detection has larger Y coordinate, this must be Pyroceram and index 1 must be WCT-2065
                            patchIdentityPossibilities[0] = [0, 0, 0, 0, 0, 0, 1, 0]
                            patchIdentityPossibilities[1] = [0, 0, 0, 0, 0, 0, 0, 1]
                        # eliminate these two patches as a possibility for other detections
                        patchIdentityPossibilities[2:, 6:8] = 0

                # Rule 3: If a detection is further away from Pyroceram or WCT-2065 than 6 times their average radius, it must not be on the PCT
                if patchIdentityPossibilities[0:2].sum() == 2:
                    # calculate average radius of large patches
                    averageLargePatchRadius = np.mean([detections[0][2], detections[1][2]])
                    # calculate average distance from this detection to large patches
                    distanceToLargePatches = np.mean([node.detectionDistances[currentDetectionIndex][0],
                                                      node.detectionDistances[currentDetectionIndex][1]])
                    # compare distance to 6x radius
                    if distanceToLargePatches > (averageLargePatchRadius * 6):
                        # set the identity possibilities for this detection to all impossible
                        patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 0, 0, 0, 0, 0, 0]

                # Rule 4: A point roughly equidistant from the Pyroceram and WCT-2065, once they are known, must only be either RG610 or OG515
                if patchIdentityPossibilities[0:2].sum() == 2:
                    # allow a 10% or 8 pixel (min radius limit) tolerance on distance difference
                    if math.isclose(node.detectionDistances[currentDetectionIndex][0],
                                    node.detectionDistances[currentDetectionIndex][1], rel_tol=0.10, abs_tol=8):
                        patchIdentityPossibilities[currentDetectionIndex] = np.logical_and([0, 1, 0, 0, 1, 0, 0, 0],
                                                                                           patchIdentityPossibilities[
                                                                                               currentDetectionIndex])
                        # Rule 5: If two detections are both either RG610 or OG515, the nearer of them on average to Pyroceram and WCT-2065 is OG515
                        for possiblePairIndex in range(0, len(detections)):
                            if np.array_equal(patchIdentityPossibilities[possiblePairIndex], [0, 1, 0, 0, 1, 0, 0,
                                                                                              0]) and possiblePairIndex is not currentDetectionIndex:
                                # if a pair with the same signature is found, check which is closer to large patches and assign signatures appropriately
                                if np.mean([node.detectionDistances[currentDetectionIndex][0],
                                            node.detectionDistances[currentDetectionIndex][1]]) < np.mean(
                                    [node.detectionDistances[possiblePairIndex][0],
                                     node.detectionDistances[possiblePairIndex][1]]):
                                    patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 0, 0, 1, 0, 0, 0]
                                    patchIdentityPossibilities[possiblePairIndex] = [0, 1, 0, 0, 0, 0, 0, 0]
                                else:
                                    patchIdentityPossibilities[possiblePairIndex] = [0, 0, 0, 0, 1, 0, 0, 0]
                                    patchIdentityPossibilities[currentDetectionIndex] = [0, 1, 0, 0, 0, 0, 0, 0]
                                # eliminate these two patches as a possibility for other detections
                                for detection in patchIdentityPossibilities:
                                    if not (np.array_equal(detection, [0, 0, 0, 0, 1, 0, 0, 0]) or np.array_equal(
                                            detection, [0, 1, 0, 0, 0, 0, 0, 0])):
                                        detection[1] = 0
                                        detection[4] = 0

                # Rule 6: If a detection is a distance away from Pyroceram or WCT-2065 larger than the average distance of a small patch to a big patch it must be NG4, RG610, or BG3
                if patchIdentityPossibilities[0:2].sum() == 2 and recursionDepth > 1:
                    if np.mean([node.detectionDistances[currentDetectionIndex][0],
                                node.detectionDistances[currentDetectionIndex][1]]) > node.averageDistanceToLargePatch:
                        patchIdentityPossibilities[currentDetectionIndex][3:6] = 0
                    # Rule 7: And opposite is true for NG11, OG515, or BG18
                    else:
                        patchIdentityPossibilities[currentDetectionIndex][0:3] = 0

                # Rule 8: If a detection is either NG11 or BG18 and Pyroceram and WCT-2065 are known, NG11 is closest to Pyroceram etc.
                if patchIdentityPossibilities[0:2].sum() == 2 and recursionDepth > 1:
                    if np.array_equal(patchIdentityPossibilities[currentDetectionIndex], [0, 0, 0, 1, 0, 1, 0, 0]):
                        # get the index of pyroceram to be able to get the distance to that detection
                        pyroceramIndex = \
                            np.where((patchIdentityPossibilities == [0, 0, 0, 0, 0, 0, 1, 0]).all(axis=1))[0][0]
                        for possibleMidPairIndex in range(0, len(detections)):
                            if np.array_equal(patchIdentityPossibilities[possibleMidPairIndex], [0, 0, 0, 1, 0, 1, 0,
                                                                                                 0]) and possibleMidPairIndex is not currentDetectionIndex:
                                # if a pair with the same signature is found, check which is closer to pyroceram and assign signatures appropriately
                                if node.detectionDistances[currentDetectionIndex][pyroceramIndex] < \
                                        node.detectionDistances[possibleMidPairIndex][pyroceramIndex]:
                                    patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 0, 1, 0, 0, 0, 0]
                                    patchIdentityPossibilities[possibleMidPairIndex] = [0, 0, 0, 0, 0, 1, 0, 0]
                                else:
                                    patchIdentityPossibilities[possibleMidPairIndex] = [0, 0, 0, 1, 0, 0, 0, 0]
                                    patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 0, 0, 0, 1, 0, 0]

                # Rule 9: If a detection is either NG4 or BG3 and NG11 or BG18 are known, NG4 is closest to NG11 etc.
                if not np.array_equal(np.where((patchIdentityPossibilities == [0, 0, 0, 1, 0, 0, 0, 0]).all(axis=1))[0],
                                      []) and recursionDepth > 1:
                    if np.array_equal(patchIdentityPossibilities[currentDetectionIndex], [1, 0, 1, 0, 0, 0, 0, 0]):
                        # get the index of ng4 to be able to get the distance to that detection
                        ng4Index = np.where((patchIdentityPossibilities == [0, 0, 0, 1, 0, 0, 0, 0]).all(axis=1))[0][0]
                        for possibleTopPairIndex in range(0, len(detections)):
                            if np.array_equal(patchIdentityPossibilities[possibleTopPairIndex], [1, 0, 1, 0, 0, 0, 0,
                                                                                                 0]) and possibleTopPairIndex is not currentDetectionIndex:
                                # if a pair with the same signature is found, check which is closer to ng4 and assign signatures appropriately
                                if node.detectionDistances[currentDetectionIndex][ng4Index] < \
                                        node.detectionDistances[possibleTopPairIndex][ng4Index]:
                                    patchIdentityPossibilities[currentDetectionIndex] = [1, 0, 0, 0, 0, 0, 0, 0]
                                    patchIdentityPossibilities[possibleTopPairIndex] = [0, 0, 1, 0, 0, 0, 0, 0]
                                else:
                                    patchIdentityPossibilities[possibleTopPairIndex] = [1, 0, 0, 0, 0, 0, 0, 0]
                                    patchIdentityPossibilities[currentDetectionIndex] = [0, 0, 1, 0, 0, 0, 0, 0]

            # Rule 10: If any detection identity is certain, eliminate that possibility from all other detections
            if patchIdentityPossibilities[currentDetectionIndex].sum() == 1:
                # Determine which identity is the one that has been solved
                identifiedIndex = np.where(patchIdentityPossibilities[currentDetectionIndex] == 1)[0][0]
                # Go through each detection and if the index doesn't match the current working one, change that identity possibility to 0
                for comparedDetectionIndex in range(0, len(patchIdentityPossibilities)):
                    if comparedDetectionIndex != currentDetectionIndex:
                        patchIdentityPossibilities[comparedDetectionIndex][identifiedIndex] = 0

        # return the identity possibilities array if either each detection only has one possibility left or max recursion reached
        if patchIdentityPossibilities.sum() == len(detections) or recursionDepth >= 10:
            return patchIdentityPossibilities
        # if not solved yet, keep recursing over the rules as some rely on other identity certainties
        else:
            return self.identitySolve(node, detections, patchIdentityPossibilities, recursionDepth + 1)

    @staticmethod
    def getMeanSmallPatchSize(d):
        """Guess patch size. It's calculated from existing detections and used to fill in
        the radii of interpolated patches. We don't actually use the big patch size, since those two patches
        must be detected."""
        smallPatchRadii = [x.r for x in (d.RG610, d.OG515, d.BG18, d.BG3, d.NG4, d.NG11) if x is not None]
        # we shrink these down, because we're using them to calculate the size of the small patches.
        # 18/30 is the ratio of the small patch size to the big patch size
        bigPatchRadii = [x.r * (18.0 / 30.0) for x in (d.Pyroceram, d.WCT2065) if x is not None]
        patchRadii = smallPatchRadii + bigPatchRadii
        return np.mean(patchRadii)

    def interpolateMissingDetections(self, node, existingDetections, recursionsLeft):
        """
        Set of rules that is recursively applied if not all PCT patches were initially identified to predict missing patch locations
        """
        # We'll go through patch by patch, checking if it is null, and if it is trying to predict it with relevant rules
        # No interpolation is attempted for Pyroceram or WCT-2065 - these are essential for the detection solver and without 
        # them detected no other patches can be predicted, and parameter adjustment will yield better results

        # first, calculate the mean sizes of big and small patches; we'll need those to create the ROIs.
        d = node.detections
        node.meanSmallPatchRadius = self.getMeanSmallPatchSize(d)

        ##### NG4 #####
        if d.NG4 is None:
            # NG4 Rule 1: If RG610 & BG3 identified, NG4 = 2 x BG3 > RG610 translation
            d.NG4, existingDetections = self.interpolationTranslation(node, "NG4", d.BG3,
                                                                      d.RG610, 1,
                                                                      existingDetections)
            if d.NG4 is None:
                # NG4 Rule 2: If RG610, NG11, & OG515 identified, NG4 = 4th corner of parallelogram
                d.NG4, existingDetections = self.interpolationMissingParallelogramCorner(node, "NG4",
                                                                                         d.RG610, d.OG515, d.NG11,
                                                                                         existingDetections)

        ##### RG610 #####
        if d.RG610 is None:
            # RG610 Rule 1: If NG4 & BG3 identified, RG610 = mean of NG4 & BG3
            d.RG610, existingDetections = self.interpolationMean(node, "RG610", d.NG4, d.BG3,
                                                                 existingDetections)

            if d.RG610 is None:
                # RG610 Rule 2: If OG515 identified, RG610 = 1.8 x mean(Pyroceram, WCT-2065) > OG515 translation
                meanLargePatchCoordinates = [int((d.Pyroceram.x + d.WCT2065.x) / 2),
                                             int((d.Pyroceram.y + d.WCT2065.y) / 2)]
                d.RG610, existingDetections = self.interpolationTranslation(node, "RG610",
                                                                            meanLargePatchCoordinates,
                                                                            d.OG515, 0.8,
                                                                            existingDetections)

        ##### BG3 #####
        if d.BG3 is None:
            # BG3 Rule 1: If RG610 & NG4 identified, BG3 = 2 x NG4 > RG610 translation
            d.BG3, existingDetections = self.interpolationTranslation(node, "BG3", d.NG4,
                                                                      d.RG610, 1,
                                                                      existingDetections)

            if d.BG3 is None:
                # BG3 Rule 2: If RG610, BG18, & OG515 identified, NG4 = 4th corner of parallelogram
                d.BG3, existingDetections = self.interpolationMissingParallelogramCorner(node, "BG3",
                                                                                         d.RG610, d.OG515, d.BG18,
                                                                                         existingDetections)

        ##### NG11 #####
        if d.NG11 is None:
            # NG11 Rule 1: If OG515 & BG18 identified, NG11 = 2 x BG18 > OG515 translation
            d.NG11, existingDetections = self.interpolationTranslation(node, "NG11", d.BG18,
                                                                       d.OG515, 1,
                                                                       existingDetections)

            if d.NG11 is None:
                # NG11 Rule 2: If RG610, NG4, & OG515 identified, NG11 = 4th corner of parallelogram
                d.NG11, existingDetections = self.interpolationMissingParallelogramCorner(node, "NG11",
                                                                                          d.OG515, d.RG610, d.BG18,
                                                                                          existingDetections)

        ##### OG515 #####
        if d.OG515 is None:
            # OG515 Rule 1: If NG11 & BG18 identified, OG515 = mean of NG11 & BG18
            d.OG515, existingDetections = self.interpolationMean(node, "OG515",
                                                                 d.NG11,
                                                                 d.BG18, existingDetections)

            if d.OG515 is None:
                # OG515 Rule 2: If RG610 identified, OG515 = 0.56 x mean(Pyroceram, WCT-2065) > RG610 translation
                meanLargePatchCoordinates = [int((d.Pyroceram.x + d.WCT2065.x) / 2),
                                             int((d.Pyroceram.y + d.WCT2065.y) / 2)]
                d.OG515, existingDetections = self.interpolationTranslation(node, "OG515",
                                                                            meanLargePatchCoordinates,
                                                                            d.RG610, -0.44,
                                                                            existingDetections)

        ##### BG18 #####
        if d.BG18 is None:
            # BG18 Rule 1: If OG515 & NG11 identified, BG18 = 2 x NG11 > OG515 translation
            d.BG18, existingDetections = self.interpolationTranslation(node, "BG18",
                                                                       d.NG11,
                                                                       d.OG515, 1,
                                                                       existingDetections)

            if d.BG18 is None:
                # BG18 Rule 2: If RG610, BG3, & OG515 identified, BG18 = 4th corner of parallelogram
                d.BG18, existingDetections = self.interpolationMissingParallelogramCorner(
                    node, "BG18", d.BG3, d.RG610, d.OG515, existingDetections)

        # check and update pct datum for completeness
        d.updateCompleteness()

        # if the datum is complete or max recursions was reached return the updated detections list now
        if d.complete or recursionsLeft <= 0:
            return existingDetections
        # if not, loop the interpolation rules again to take advantage of identities detected this time
        else:
            return self.interpolateMissingDetections(node, existingDetections, recursionsLeft - 1)

    def checkExistingDetections(self, predictedXY, comparisonDetections):
        """
        Check if a set of predicted coordinates have a close pair already in a detections list and if so replace them with the existing set
        """
        coordinatesReplaced = False
        # loop through every existing detection
        for comparisonCoordinate in comparisonDetections:
            # if the euclidian distance between the predicted and comparison coordinates is small enough they are likely the same patch
            # small enough here is a triangle with 8 difference on the x and y, 11.314 is the hypotenuse
            if math.dist((comparisonCoordinate[0], comparisonCoordinate[1]),
                         (predictedXY[0], predictedXY[1])) <= 11.314:
                predictedXY = [comparisonCoordinate[0], comparisonCoordinate[1]]
                # mark the coordinates as replaced to say if this was a native detection or not
                coordinatesReplaced = True

        return predictedXY, coordinatesReplaced

    def interpolationMean(self, node, label, patchOne, patchTwo, existingDetections):
        """
        Predict a target patch as the mean of two other patches
        """
        # check the translation components are not null
        if None not in (patchOne, patchTwo):
            patchOne = toPair(patchOne)
            patchTwo = toPair(patchTwo)

            predictedXY = [int((patchOne[0] + patchTwo[0]) / 2),
                           int((patchOne[1] + patchTwo[1]) / 2)]
            # check if any exiting detections closely match the coordinates and use those instead if so
            predictedXY, replaced = self.checkExistingDetections(predictedXY, existingDetections)
            # if the predicted coordinates were a new detection, add to the detections array with a tag that it was a interpolated detection
            if not replaced:
                existingDetections.append([predictedXY[0], predictedXY[1], node.meanSmallPatchRadius, False])
            # return the coordinates for the patch to the datum and the detections array
            return createInterpolatedROI(predictedXY[0], predictedXY[1], node.meanSmallPatchRadius,
                                         label), existingDetections
        # if the translation components were null, return nothing for the patch and the detections array
        return None, existingDetections

    def interpolationTranslation(self, node, label, translationSource, translationDestination, translationMagnitude,
                                 existingDetections):
        """
        Predict a target patch relative to a translation between two other patches - a translation magnitude of 1 
        applies the current translation again from the destination.
        """
        # check the translation components are not null
        if None not in (translationSource, translationDestination):
            # this is a bit bloody unpleasant because the two positions can be either ROIs or tuples/lists!
            translationSource = toPair(translationSource)
            translationDestination = toPair(translationDestination)

            predictedXY = [translationDestination[0] + int(
                translationMagnitude * (translationDestination[0] - translationSource[0])),
                           translationDestination[1] + int(
                               translationMagnitude * (translationDestination[1] - translationSource[1]))]
            # check if any exiting detections closely match the coordinates and use those instead if so
            predictedXY, replaced = self.checkExistingDetections(predictedXY, existingDetections)
            # if the predicted coordinates were a new detection, add to the detections array with a tag that it was a interpolated detection
            if not replaced:
                existingDetections.append([predictedXY[0], predictedXY[1], node.meanSmallPatchRadius, False])
            # return the coordinates for the patch to the datum and the detections array
            return createInterpolatedROI(predictedXY[0], predictedXY[1], node.meanSmallPatchRadius,
                                         label), existingDetections
        # if the translation components were null, return nothing for the patch and the detections array
        return None, existingDetections

    def interpolationMissingParallelogramCorner(self, node, label, leftCorner, oppositeCorner, rightCorner,
                                                existingDetections):
        """
        Predict a target patch as the 4th corner of a parallelogram where 3 other patches are the known corners
        """
        # check the parallelogram corners are not null
        if None not in (leftCorner, oppositeCorner, rightCorner):
            leftCorner = toPair(leftCorner)
            oppositeCorner = toPair(oppositeCorner)
            rightCorner = toPair(rightCorner)

            predictedX = leftCorner[0] + (rightCorner[0] - oppositeCorner[0])
            predictedY = leftCorner[1] + (rightCorner[1] - oppositeCorner[1])
            predictedXY = [predictedX, predictedY]
            # check if any exiting detections closely match the coordinates and use those instead if so
            predictedXY, replaced = self.checkExistingDetections(predictedXY, existingDetections)
            # if the predicted coordinates were a new detection, add to the detections array with a tag that it was a interpolated detection
            if not replaced:
                existingDetections.append([predictedXY[0], predictedXY[1], node.meanSmallPatchRadius, False])
            # return the coordinates for the patch to the datum and the detections array
            return createInterpolatedROI(predictedXY[0], predictedXY[1], node.meanSmallPatchRadius,
                                         label), existingDetections
        # if the translation components were null, return nothing for the patch and the detections array
        return None, existingDetections

    def detectFlippage(self, node):
        """Detect whether the set of detections is flipped around the PCT's vertical axis. In the correct
        orientation, the Pyroceram patch should always be clockwise from the WCT2065 patch. If the Pyroceram
        patch is anticlockwise, the image is flipped and the detections need to be flipped back."""

        # first find the centroid of all the patches around the edge of the image (i.e. not OG515 or
        # RG610)
        centroid = node.detections.findEdgeCentroid()
        if centroid is None:
            # not enough patches were detected, return without doing anything
            return

        def getAngle(cc, p):
            """Find the angle between the centroid and a patch"""
            if cc is None or p is None:
                return None
            cx, cy = cc
            return math.atan2(p.y - cy, p.x - cx)

        angleWCT2065 = getAngle(centroid, node.detections.WCT2065)
        anglePyroceram = getAngle(centroid, node.detections.Pyroceram)
        angleNG11 = getAngle(centroid, node.detections.NG11)
        angleNG4 = getAngle(centroid, node.detections.NG4)
        angleRG610 = getAngle(centroid, node.detections.RG610)
        angleNG3 = getAngle(centroid, node.detections.BG3)
        angleBG18 = getAngle(centroid, node.detections.BG18)

        # now go around the edge of the image in order, checking that each patch is clockwise from the
        # previous one, and incrementing or decrementing a count depending on whether it is or not

        ct = 0

        def checkAngle(a1, a2):
            """Ensuring that both angles are not None (and therefore both patches have been detected),
            increment or decrement the count depending on whether the first angle is less than the second"""
            nonlocal ct
            if a1 is not None and a2 is not None:
                ct += 1 if a1 < a2 else -1

        checkAngle(angleWCT2065, anglePyroceram)
        checkAngle(anglePyroceram, angleNG11)
        checkAngle(angleNG11, angleNG4)
        checkAngle(angleNG4, angleRG610)
        checkAngle(angleRG610, angleNG3)
        checkAngle(angleNG3, angleBG18)
        checkAngle(angleBG18, angleWCT2065)

        # if the count is negative, the image is flipped
        if ct < 0:
            # here we flip the detections around the vertical axis
            node.detections.flip()


####################################################################################################

# This class defines the graphical appearance of the node
class TabPCTPatchDetection(Tab):
    """
    Class defining the visual states of the pct detection node
    """

    def __init__(self, node, window):
        """
        Initialise the GUI and connect elements to back-end functions
        """
        super().__init__(window, node, 'tabpctdetection.ui')

        # sync tab with node
        self.nodeChanged()

        ### Patch Descriptions Widget### 
        # register the pct description image scene
        descriptionImageScene = QGraphicsScene()

        # look for the patch description image basd on location of this file to allow node to run in different places
        fileLocation, _ = path.split(__file__)
        pixmapDescImageScene = QPixmap.fromImage(
            QImage(path.join(fileLocation, "../assets/images/patchdescriptions.png")))
        descriptionImageScene.addItem(QGraphicsPixmapItem(pixmapDescImageScene.scaled(QSize(190, 190))))

        # Set the text or image onto the patch description view window
        self.w.pctpatchdiagram.setScene(descriptionImageScene)

        ### Node Description Widget###
        # load node description section
        self.w.nodeDescription.setText(
            "This node is used to automatically detect PCT patches in ExoMars PanCam images. " +
            "Green single-line circles represent native detections and blue multi-line " +
            "circles represent predicted patch locations where the patch was obscured or undetected. " +
            "If manual input to resolve undetected patches is needed, unlock the detection paramaters.")

        ### Detection Parameters Widget###                    
        # setup parameter lock checkbox to spawn locked
        self.w.lockParametersCheckBox.setChecked(node.parametersLocked)
        # and connect it to function to toggle operability of all sliders
        self.w.lockParametersCheckBox.stateChanged.connect(self.lockToggleClick)

        # initialise parameter sliders
        self.initParamSliders()
        self.setDefaultSliderValues()

        # connect each slider to it's respective parameter in the node
        self.w.dpSlider.valueChanged.connect(self.changeDPValue)
        self.w.minDistSlider.valueChanged.connect(self.changeMinDistValue)
        self.w.cannyHighSlider.valueChanged.connect(self.changeCannyHighValue)
        self.w.cannyLowSlider.valueChanged.connect(self.changeCannyLowValue)
        self.w.minRadiusSlider.valueChanged.connect(self.changeMinRadiusValue)
        self.w.maxRadiusSlider.valueChanged.connect(self.changeMaxRadiusValue)

        # connect buttons to reset to defaults and to show parameter descriptions to functions
        self.w.resetDefaultsPushButton.clicked.connect(self.setDefaultSliderValues)
        self.w.parameterDescButton.clicked.connect(self.showParameterDescriptionsPopup)

    def initParamSliders(self):
        """
        Initialise the parameters of the parameter sliders in the parameters widget
        """
        # DP
        # TODO: work out system to use floats for sliders - qslider only uses ints
        self.w.dpSlider.setMinimum(1)
        self.w.dpSlider.setMaximum(3)
        self.w.dpSlider.setSingleStep(1)
        self.w.dpSlider.setEnabled(False)
        self.w.dpSlider.setTracking(False)
        # Mimimum Distance
        self.w.minDistSlider.setMinimum(5)
        self.w.minDistSlider.setMaximum(100)
        self.w.minDistSlider.setSingleStep(1)
        self.w.minDistSlider.setEnabled(False)
        self.w.minDistSlider.setTracking(False)
        # Canny High Parameter
        self.w.cannyHighSlider.setMinimum(20)
        self.w.cannyHighSlider.setMaximum(400)
        self.w.cannyHighSlider.setSingleStep(1)
        self.w.cannyHighSlider.setEnabled(False)
        self.w.cannyHighSlider.setTracking(False)
        # Canny Low Parameter
        self.w.cannyLowSlider.setMinimum(10)
        self.w.cannyLowSlider.setMaximum(200)
        self.w.cannyLowSlider.setSingleStep(1)
        self.w.cannyLowSlider.setEnabled(False)
        self.w.cannyLowSlider.setTracking(False)
        # Minimum Radius
        self.w.minRadiusSlider.setMinimum(1)
        self.w.minRadiusSlider.setMaximum(100)
        self.w.minRadiusSlider.setSingleStep(1)
        self.w.minRadiusSlider.setEnabled(False)
        self.w.minRadiusSlider.setTracking(False)
        # Maximum Radius
        self.w.maxRadiusSlider.setMinimum(5)
        self.w.maxRadiusSlider.setMaximum(250)
        self.w.maxRadiusSlider.setSingleStep(1)
        self.w.maxRadiusSlider.setEnabled(False)
        self.w.maxRadiusSlider.setTracking(False)

    def setDefaultSliderValues(self):
        """
        Set the parameter slider values to the 'default' values, used at init and by reset to default button
        """
        self.mark()
        # DP
        self.w.dpSlider.setValue(DP)
        # Mimimum Distance
        self.w.minDistSlider.setValue(MINDISTANCE)
        # Canny High Parameter
        self.w.cannyHighSlider.setValue(CANNYHIGHPARAM)
        # Canny Low Parameter
        self.w.cannyLowSlider.setValue(CANNYLOWPARAM)
        # Minimum Radius
        self.w.minRadiusSlider.setValue(MINRADIUS)
        # Maximum Radius
        self.w.maxRadiusSlider.setValue(MAXRADIUS)
        self.changed()

    def lockToggleClick(self):
        """
        Lock the interactibility of the parameter sliders while the parameter lock checkbox is ticked
        and vice versa
        """
        self.mark()
        # update the node variable
        self.node.parametersLocked = self.w.lockParametersCheckBox.isChecked()
        # lock parameter sliders if checkbox is checked
        if self.w.lockParametersCheckBox.isChecked():
            self.w.dpSlider.setEnabled(False)
            self.w.minDistSlider.setEnabled(False)
            self.w.cannyHighSlider.setEnabled(False)
            self.w.cannyLowSlider.setEnabled(False)
            self.w.minRadiusSlider.setEnabled(False)
            self.w.maxRadiusSlider.setEnabled(False)
        # and unlock them if it isnt
        else:
            self.w.dpSlider.setEnabled(True)
            self.w.minDistSlider.setEnabled(True)
            self.w.cannyHighSlider.setEnabled(True)
            self.w.cannyLowSlider.setEnabled(True)
            self.w.minRadiusSlider.setEnabled(True)
            self.w.maxRadiusSlider.setEnabled(True)

    def changeDPValue(self):
        """Links dp slider to node instance variable"""
        self.mark()
        self.node.params.dp = float(self.w.dpSlider.value())
        self.changed()

    def changeMinDistValue(self):
        """Links minDist slider to node instance variable"""
        self.mark()
        self.node.params.minDist = float(self.w.minDistSlider.value())
        self.changed()

    def changeCannyHighValue(self):
        """Links cannyHighParam slider to node instance variable"""
        self.mark()
        self.node.params.cannyHighParam = float(self.w.cannyHighSlider.value())
        self.changed()

    def changeCannyLowValue(self):
        """Links cannyLowParam slider to node instance variable"""
        self.mark()
        self.node.params.cannyLowParam = float(self.w.cannyLowSlider.value())
        self.changed()

    def changeMinRadiusValue(self):
        """Links minRadius slider to node instance variable"""
        self.mark()
        self.node.params.minRadius = self.w.minRadiusSlider.value()
        self.changed()

    def changeMaxRadiusValue(self):
        """Links maxRadius slider to node instance variable"""
        self.mark()
        self.node.params.maxRadius = self.w.maxRadiusSlider.value()
        self.changed()

    def showParameterDescriptionsPopup(self):
        """
        Spawns a popup window with descriptions of parameters if the user needs to alter them
        """
        descriptionsWindow = QMessageBox()
        descriptionsWindow.setIcon(QMessageBox.Information)
        descriptionsWindow.setStandardButtons(QMessageBox.Ok)
        descriptionsWindow.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse | Qt.TextBrowserInteraction)
        descriptionsWindow.setTextFormat(Qt.RichText)
        descriptionsWindow.setWindowTitle("Patch Detection Parameter Descriptions")
        descriptionsWindow.setText("""
DP: The inverse ratio of the accumulator resolution for the hough detections \nto the image resolution. The higher the DP, the lower the resolution of \nthe detection accumulator.
<br><br>
Minimum Distance: The minimum distance in pixels allowed between detections \nof patch centres.
<br><br>
Canny High Parameter: The higher of the two canny edge detection parameters \nused by the detector. Documentation recommends this \nis twice the lower parameter.
<br><br>
Canny Low Parameter: The lower of the two canny edge detection parameters \nused by the detector. Documentation recommends this \nis half the higher parameter.
<br><br>
Minimum Radius: The maximum radius in pixels of patch detections.
<br><br>
Maximum Radius: The minimum radius in pixels of patch detections.
<br><br>
More information can be found under the HoughCircles() method documentation <a href='https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html#ga47849c3be0d0406ad3ca45db65a25d2d'>here</a>.
        """)
        descriptionsWindow.exec_()

    def onNodeChanged(self):
        """
        This function runs each time changed() is called and updates the visual states of the node
        """
        # backwards connection from detector parameters to sliders - needed for undo stack
        self.w.dpSlider.setValue(self.node.params.dp)
        self.w.minDistSlider.setValue(self.node.params.minDist)
        self.w.cannyHighSlider.setValue(self.node.params.cannyHighParam)
        self.w.cannyLowSlider.setValue(self.node.params.cannyLowParam)
        self.w.minRadiusSlider.setValue(self.node.params.minRadius)
        self.w.maxRadiusSlider.setValue(self.node.params.maxRadius)

        # update paramater lock checkbox
        self.w.lockParametersCheckBox.setChecked(self.node.parametersLocked)

        # display image from input if one exists
        self.w.canvas.setVisible(True)
        if self.node.inputImg is not None:
            # Display mapped RGB image on canvas
            self.w.canvas.setNode(self.node)
            self.w.canvas.display(self.node.inputImg)

        # handle the detections list in the bottom left widget
        if self.node.detections is not None:
            self.w.detectionsOutput.setText(f'Detected Centre Coordinates:\n{self.node.detections}')
        else:
            self.w.detectionsOutput.setText("No Detections Made")

        # display detections subimage if one exists
        detectionsPlotScene = QGraphicsScene()
        if self.node.detectionsImage is not None:
            # register the pct description image onto the node

            # convert image array to a usable QImage
            h, w, _ = self.node.detectionsImage.shape
            bytesPerLine = 3 * w
            qImageDetectionsImage = QImage(self.node.detectionsImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
            # convert Qimage to pixmap graphics item for the scene, and scale to size for display
            detectionsPlotScene.addItem(QGraphicsPixmapItem(QPixmap.fromImage(qImageDetectionsImage)))
        self.w.detectionsPlot.setScene(detectionsPlotScene)

        # update paramater slider labels to the current value in the node
        self.w.dpValueLabel.setText(str(self.node.params.dp))
        self.w.minDistValueLabel.setText(str(self.node.params.minDist))
        self.w.cannyHighValueLabel.setText(str(self.node.params.cannyHighParam))
        self.w.cannyLowValueLabel.setText(str(self.node.params.cannyLowParam))
        self.w.minRadiusValueLabel.setText(str(self.node.params.minRadius))
        self.w.maxRadiusValueLabel.setText(str(self.node.params.maxRadius))


####################################################################################################

class PCTPatchData:
    """
    Class defining the data structure for PCT data, consisting of 8 circular ROIs in the recieved image,
    or 'None' values where patch identities couldn't be detected, and one extra variable to mark if the
    PCT data is complete (8 patches) or not. It used to be the output type of the PCTPatchDetector node,
    but now we use ROIs on the image for that.
    """

    # The variable names within this object reference the names for the glass patches on the PCT
    # These are of the form:
    #
    #                 NG4 | RG610 | BG3
    #                -----+-------+-----
    #                NG11 | OG515 | BG18
    #                -----+---+---+-----
    #                         |
    #                Pyroceram| WCT2065
    #                         |
    #
    # A view of the PCT is available at https://exomars.wales/projects/hardware/
    # Each of the patch variables should take the form [x,y] or None

    PATCHNAMES = ["NG4", "RG610", "BG3", "NG11", "OG515", "BG18", "Pyroceram", "WCT2065"]

    def __init__(self, NG4, RG610, BG3, NG11, OG515, BG18, Pyroceram, WCT2065):
        """
        Initialise a PCTPatchData datum from a set of patch centre detections or nulls. Contains centre coords
        and radii.
        """

        def patch2circ(patch, label):
            # generates an ROI from a patch, giving it a label and setting the font size
            if patch is None:
                return None
            r = ROICircle(patch[0], patch[1], patch[2], label=label)
            r.fontsize = 6
            return r

        # build the ROIs from the patches
        # We label these with tentative labels - the real labels will be set later because they could get "flipped".
        self.NG4 = patch2circ(NG4, "NG4")
        self.RG610 = patch2circ(RG610, "RG610")
        self.BG3 = patch2circ(BG3, "BG3")
        self.NG11 = patch2circ(NG11, "NG11")
        self.OG515 = patch2circ(OG515, "OG515")
        self.BG18 = patch2circ(BG18, "BG18")
        self.Pyroceram = patch2circ(Pyroceram, "Pyroceram")
        self.WCT2065 = patch2circ(WCT2065, "WCT2065")

        # if None isn't present in any inputs, the data is complete, and the datum can be marked so
        # this makes life easier down the processing line not having to do this same check many times
        if None not in self.toROIList():
            self.complete = True
        else:
            self.complete = False

    def findEdgeCentroid(self):
        """Find the centroid of the edge patches of the PCT which have been detected. If less than 2 edge patches have
        been detected, return None. The edge patches are all patches excluding OG515 and RG610"""

        # create a list of the patches excluding OG515 and RG610
        patches = [self.NG4, self.BG3, self.NG11, self.BG18, self.Pyroceram, self.WCT2065]

        # create a list of the patches which have been detected
        detectedPatches = [patch for patch in patches if patch is not None]

        # if less than 2 patches have been detected, return None
        if len(detectedPatches) < 2:
            return None

        # find the centroid of the detected patches
        x = 0
        y = 0
        for patch in detectedPatches:
            x += patch.x
            y += patch.y
        x /= len(detectedPatches)
        y /= len(detectedPatches)

        return x, y

    def flip(self):
        """Flip the detections around the vertical axis"""
        self.Pyroceram, self.WCT2065 = self.WCT2065, self.Pyroceram
        self.BG18, self.NG11 = self.NG11, self.BG18
        self.BG3, self.NG4 = self.NG4, self.BG3

    def __str__(self):
        """Return a string representation of the PCTPatchData"""

        def patch2str(patch):
            return f"{patch.x}, {patch.y}, {patch.r}" if patch is not None else "None"

        lst = [f"{name}: {patch2str(patch)}" for name, patch in zip(self.PATCHNAMES, self.toROIList())]
        return "\n".join(lst)

    def updateCompleteness(self):
        """
        Method to be called to check if the datum holds all patch detections, and update the datum variable if so
        """
        # if all variables are populated the datum is complete
        if None not in self.toROIList():
            self.complete = True
        else:
            self.complete = False

    def labelROIs(self):
        """Label the ROIs with the correct patch names; they may have been flipped"""
        for name in self.PATCHNAMES:
            patch = getattr(self, name)
            if patch is not None:
                patch.label = name

    def toROIList(self):
        """return a list of the patches in the order of the patch names"""
        lst = [getattr(self, name) for name in self.PATCHNAMES]
        # just make sure the names are correct
        for name, patch in zip(self.PATCHNAMES, lst):
            if patch is not None and patch.label != name:
                raise ValueError(f"Patch name {name} does not match label {patch.label}")
        return lst
