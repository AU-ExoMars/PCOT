from copy import copy

from pcot.datum import Datum
from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabdata import TabData


def modifyROISize(roi, img):
    roi = copy(roi)
    roi.setContainingImageDimensions(img.w, img.h)
    return roi


@xformtype
class XformImportROI(XFormType):
    """
    Import a ROI into an image which was originally set on another image. The 'roi' input takes
    either an ROI or an image. If the former, that ROI is imposed on the image passed into the main
    input. If the latter, all the ROIs from the 'roi' input image are imposed on the image input
    image."""

    def __init__(self):
        super().__init__("importroi", "ROI edit", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addInputConnector("roi", Datum.ANY)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        return TabData(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node, x=None):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            roiinput = node.getInput(1)
            if roiinput is not None:
                # make a clone of the input image
                img = img.copy()
                if roiinput.tp == Datum.IMG:
                    # if the ROI input is an image, add that image's ROIs to ours
                    img.rois += [modifyROISize(x, img) for x in roiinput.val.rois if x is not None]
                elif roiinput.tp == Datum.ROI:
                    # otherwise if it's an ROI, append the ROI to ours.
                    if roiinput.val is not None:
                        img.rois.append(modifyROISize(roiinput.val, img))
                    else:
                        raise XFormException('DATA', 'ROI input is None')
                else:
                    raise XFormException('DATA', "bad type: must be ROI or image on 'roi' input")

        node.setOutput(0, Datum(Datum.IMG, img))
