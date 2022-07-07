import pcot
from pcot.datum import Datum
from pcot.xform import xformtype, XFormType, XFormException


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
        t = TabImportROI(n, w)
        # modify the canvas to show own-ROI data
        t.w.canvas.setROINode(n)
        return t

    def init(self, node):
        node.img = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        node.roi = None
        rgb = None
        if img is not None:
            roiinput = node.getInput(1)
            if roiinput is not None:
                img = img.copy()
                if roiinput.tp == Datum.IMG:
                    img.rois += roiinput.val.rois
                elif roiinput.tp == Datum.ROI:
                    img.rois.append(roiinput.val)
                    node.roi = roiinput.val
                else:
                    raise XFormException('DATA', "bad type: must be ROI or image on 'roi' input")
            # create a premapped rgb image for the canvas and give it the same ROIs as the main image
            # (so the pixel counts will still work)
            rgb = img.rgbImage()
            rgb.rois = img.rois
            img.drawROIs(rgb.img, onlyROI=None if node.showROIs else node.roi)

        node.img = img
        node.rgbImage = rgb  # the RGB image shown in the canvas (using the "premapping" idea)

        node.setOutput(0, Datum(Datum.IMG, img))

    def getROIDesc(self, node):
        return "no ROI" if node.roi is None else node.roi.details()


class TabImportROI(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabdata.ui')
        self.w.canvas.setPersister(node)
        # sync tab with node
        self.nodeChanged()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setVisible(True)  # this is the generic data viewer, but we're just using it for images.
        self.w.textEdit.setVisible(False)
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
