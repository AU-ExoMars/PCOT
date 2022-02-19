from pcot.datum import Datum
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabimage import TabImage


# The node type itself, a subclass of XFormType with the @xformtype decorator which will
# calculate a checksum of this source file and automatically create the only instance which
# can exist of this class (it's a singleton).

@xformtype
class XformSink(XFormType):
    """Simply view an image."""

    def __init__(self):
        # call superconstructor with the type name and version code
        super().__init__("sink", "utility", "0.0.0")
        # set up a single input which takes an datum of any type. The connector could have
        # a name in more complex node types, but here we just have an empty string.
        self.addInputConnector("", Datum.ANY)

    # this creates a tab when we want to control or view a node of this type. This uses
    # the built-in TabImage, which contains an OpenCV image viewer.
    def createTab(self, n, w):
        return TabImage(n, w)

    # actually perform a node's action, which happens when any of the nodes "upstream" are changed
    # and on loading.
    def perform(self, node):
        # get the input (index 0, our first and only input). That's all - we just store a reference
        # to the image in the node. The TabImage knows how to display nodes with "out" attributes,
        # and does the rest.
        out = node.getInput(0)
        if out is not None:
            # if it's an image we need to use a copy using this node's mapping
            if out.isImage():
                outimg = out.val.copy()
                outimg.mapping = node.mapping
                out = Datum(Datum.IMG, outimg)
        node.out = out

    def init(self, node):
        # initialise the node by setting its img to None.
        node.out = None
