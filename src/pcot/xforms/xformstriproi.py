from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabdata import TabData


@xformtype
class XformStripROI(XFormType):
    """Strip ROIs from an image"""

    def __init__(self):
        # this node is called "striproi", it lives in the "ROI edit"
        # group in the palette, and the version number is "0.0.0".
        super().__init__("striproi", "ROI edit", "0.0.0")
        # it has a single input, which is unnamed and is an image
        self.addInputConnector("", Datum.IMG)
        # it has a single output, which is unnamed and is an image
        self.addOutputConnector("", Datum.IMG)
        # it has no parameters, so we create an empty TaggedDictType
        self.params = TaggedDictType()

    def createTab(self, n, w):
        # it doesn't use a custom tab - just the standard tab for
        # showing images (maybe later this will show other data types too)
        return TabData(n, w)

    def init(self, node):
        # the node stores no state data - the output image will be accessed by the tab.
        pass

    def perform(self, node):
        # when we run the node, we get the node's only input - an image.
        # Calling getInput() with a type will check it's of the right type
        # and will also "unwrap" it, so this returns an ImageCube rather
        # than a Datum. If the type is wrong, we get None.
        out = node.getInput(0, Datum.IMG)
        if out is not None:
            # all is well - make a copy of the ImageCube we got, but
            # set its list of regions to empty.
            out = out.copy()
            # We have to tell the image to use the node's mapping, or the canvas
            # will not respond to mapping changes
            out.mapping = node.mapping
            out.rois = []
        # build a new Datum to hold the output, and output it. The TabData will read this.
        node.setOutput(0, Datum(Datum.IMG, out))
