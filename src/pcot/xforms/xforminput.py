from pcot.datum import Datum
import pcot.inputs

from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabdata import TabData


class XFormInput(XFormType):
    """Bring an input into the graph."""
    def __init__(self, idx):
        super().__init__("input " + str(idx), "source", "0.0.0")
        self.addOutputConnector("", Datum.NONE)   # this changes type dynamically
        self.idx = idx

    def createTab(self, n, w):
        return TabData(n, w)

    def init(self, node):
        node.out = None

    def perform(self, node):
        # get hold of the document via the graph, get the input manager, and access
        # the input.
        inp = node.graph.doc.inputMgr.inputs[self.idx]
        out = inp.get()
        if out.isNone():
            # if the input is None, and it's not the Null input, set an error state (but not an exception)
            if inp.activeMethod != pcot.inputs.Input.NULL:
                node.setError(XFormException('DATA', 'input node could not read data - {}'.format(inp.exception)))
        else:
            out = out.copy()   # make a copy of the input (usually doesn't actually copy)
            if out.isImage():
                out.val.setMapping(node.mapping)

        node.changeOutputType(0, out.tp)

        node.out = out
        node.setOutput(0, node.out)


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
