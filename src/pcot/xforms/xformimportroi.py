from copy import copy

from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.rois import ROICOLOURTYPE
from pcot.ui.tabs import Tab
from pcot.xform import xformtype, XFormType, XFormException
import pcot.utils.colour


def copy_and_modify_roi(roi, img, new_name=None, new_colour=None):
    roi = copy(roi)
    roi.setContainingImageDimensions(img.w, img.h)
    if new_name is not None and new_name != "":
        # rename the ROI if a new name is provided
        roi.label = new_name
    if new_colour is not None:
        # unpack the colour TaggedDict into a tuple
        roi.colour = (new_colour.r, new_colour.g, new_colour.b)
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
        self.params = TaggedDictType(
            new_name=("new name for the ROI if non-empty", str, ""),
            new_colour=("the new colour of the ROI", ROICOLOURTYPE),
            recolour=("change colour to new colour", bool, False),
        )

    def createTab(self, n, w):
        return ImportROITab(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node, x=None):
        img = node.getInput(0, Datum.IMG)
        new_name = node.params.new_name
        node.setRectText(new_name)
        new_colour = node.params.new_colour if node.params.recolour else None

        if img is not None:
            roiinput = node.getInput(1)
            if roiinput is not None:
                # make a clone of the input image
                img = img.copy()
                if roiinput.tp == Datum.IMG:
                    # if the ROI input is an image, add that image's ROIs to ours
                    img.rois += [copy_and_modify_roi(x, img, new_name, new_colour) for x in roiinput.val.rois if x is not None]
                elif roiinput.tp == Datum.ROI:
                    # otherwise if it's an ROI, append the ROI to ours.
                    if roiinput.val is not None:
                        img.rois.append(copy_and_modify_roi(roiinput.val, img, new_name, new_colour))
                    else:
                        raise XFormException('DATA', 'ROI input is None')
                else:
                    raise XFormException('DATA', "bad type: must be ROI or image on 'roi' input")

        node.setOutput(0, Datum(Datum.IMG, img))


class ImportROITab(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabimportroi.ui')
        self.w.newName.textChanged.connect(self.setNewName)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.recolourBox.toggled.connect(self.recolourChanged)

        self.nodeChanged()

    def setNewName(self, v):
        self.mark()
        self.node.params.new_name = v
        self.changed()

    def recolourChanged(self, checked):
        self.mark()
        self.node.params.recolour = checked
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.params.new_colour)
        if col is not None:
            self.mark()
            # the colour is a TaggedDictType, but we have received a tuple.
            # We need to set the r, g, b values in the TaggedDict. The set()
            # method will do this by unpacking the tuple; it sets each argument
            # it gets to the corresponding key in the TaggedDict (the dict has
            # to be ordered for this to work, which it is).
            self.node.params.new_colour.set(*col)
            self.changed()

    def nodeChanged(self):
        # sync tab with node
        self.w.newName.setText(self.node.params.new_name)

        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.getOutput(0, Datum.IMG))
