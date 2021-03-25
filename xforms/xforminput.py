import conntypes
from xform import xformtype, XFormType, XForm, Datum
from xforms.tabimage import TabImage


class XFormInput(XFormType):
    def __init__(self, idx):
        super().__init__("input " + str(idx), "source", "0.0.0")
        self.addOutputConnector("img", "img", "image")
        self.idx = idx

    def createTab(self, n, w):
        return TabImage(n, w)

    def init(self, node):
        node.img = None

    def perform(self, node):
        node.img = node.graph.inputMgr.inputs[self.idx].get()
        if node.img is not None:
            node.img.setMapping(node.mapping)
        node.setOutput(0, Datum(conntypes.IMG, node.img))


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
