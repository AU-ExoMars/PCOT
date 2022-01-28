from pcot.datum import Datum
import pcot.inputs
from pcot.imagecube import ImageCube

from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabimage import TabImage


class XFormInput(XFormType):
    """Bring an input into the graph."""
    def __init__(self, idx):
        super().__init__("input " + str(idx), "source", "0.0.0")
        self.addOutputConnector("img", Datum.IMG, "image")
        self.idx = idx

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        # get hold of the document via the graph, get the input manager, and access
        # the input.
        inp = node.graph.doc.inputMgr.inputs[self.idx]
        node.img = inp.get()
        if isinstance(node.img, ImageCube):
            node.img.setMapping(node.mapping)
            node.setOutput(0, Datum(Datum.IMG, node.img))
        elif inp.activeMethod != pcot.inputs.Input.NULL:
            node.setError(XFormException('DATA', 'input node could not read data - {}'.format(inp.exception)))
            node.setOutput(0, None)


@xformtype
class XFormInput0(XFormInput):
    """Imports Input 0's data into the graph"""

    def __init__(self):
        super().__init__(0)


@xformtype
class XFormInput1(XFormInput):
    """Imports Input 1's data into the graph"""

    def __init__(self):
        super().__init__(1)


@xformtype
class XFormInput2(XFormInput):
    """Imports Input 2's data into the graph"""

    def __init__(self):
        super().__init__(2)


@xformtype
class XFormInput3(XFormInput):
    """Imports Input 3's data into the graph"""

    def __init__(self):
        super().__init__(3)
