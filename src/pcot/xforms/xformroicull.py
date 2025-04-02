from PySide2.QtCore import Qt
from PySide2.QtWidgets import QListWidgetItem

from pcot.ui.tabs import Tab
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType
from pcot.xform import XFormType, xformtype


@xformtype
class ROICull(XFormType):
    """
    This node allows certain ROIs to be removed from the input image by name.
    """
    def __init__(self):
        super().__init__("roicull", "ROI edit", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

        self.params = TaggedDictType(
            rois=("ROIs to Cull", TaggedListType(str, [], '')),
            cullbad=("Cull bad ROIs (ROIs with all pixels BAD in any band)", bool, False),
        )

    def init(self, node):
        pass

    def createTab(self, n, window):
        # Create the tab for this node
        return TabROICull(n, window)

    def perform(self, node):
        # Get the input image
        img = node.getInput(0, Datum.IMG)
        node.rois = []

        if img is not None:
            # get the ROIs from the input image, filtering out the bad ones if needed
            img_rois = img.filterBadROIs() if node.params.cullbad else img.rois
            # our output is the input image with the ROIs removed.
            img = img.shallowCopy()
            rois_to_cull = node.params.rois
            # we make a copy of the input image's ROIs so we don't lose them
            # when we delete them from the image! This is the set used by the UI.
            node.rois = img_rois.copy()
            # remove the ROIs which are in the list of ROIs to cull
            img.rois = [
                roi for roi in img_rois if roi.label not in rois_to_cull
            ]
            node.setOutput(0, Datum(Datum.IMG, img))
        else:
            node.setOutput(0, Datum.null)
        # and we display the output which will have the ROIs removed
        node.img = img


class TabROICull(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabroicull.ui')
        self.w.roiList.itemChanged.connect(self.onROIListItemChanged)
        self.w.checkCullBad.stateChanged.connect(self.onCullBadStateChanged)
        self.w.canvas.setNode(node)
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.roiList.clear()
        selected_rois = self.node.params.rois
        for roi in self.node.rois:
            item = QListWidgetItem(roi.label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if roi.label in selected_rois else Qt.Unchecked)
            self.w.roiList.addItem(item)
        self.w.checkCullBad.setChecked(self.node.params.cullbad)
        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.img)

    def onROIListItemChanged(self, item):
        if item.checkState() == Qt.Checked:
            self.node.params.rois.append(item.text())
        else:
            self.node.params.rois.remove(item.text())
        self.changed()

    def onCullBadStateChanged(self):
        self.node.params.cullbad = self.w.checkCullBad.isChecked()
        self.changed()

