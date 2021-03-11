from xform import xformtype, XFormType, XForm
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
        node.setOutput(0, node.img)


@xformtype
class XFormInput0(XFormInput):
    def __init__(self):
        super().__init__(0)


@xformtype
class XFormInput1(XFormInput):
    def __init__(self):
        super().__init__(1)


@xformtype
class XFormInput2(XFormInput):
    def __init__(self):
        super().__init__(2)


@xformtype
class XFormInput3(XFormInput):
    def __init__(self):
        super().__init__(3)
