import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import nullSourceSet
from pcot.value import OpData
from pcot.xform import XFormType, BadTypeException, xformtype


def test_nodes_run():
    """Just make sure all nodes can perform without inputs. This could be made to pass by just
    having create() do nothing, or having perform() do nothing, but them's the breaks."""
    pcot.setup()
    for x in XFormType.all():
        doc = Document()            # create document
        doc.graph.create(x)  # create the node (there will also be an "input", ignore it).
        doc.graph.performNodes()    # perform all nodes


def test_node_output_none():
    """Test every XForm type by creating an empty document with one node of that type, and ensure it
    produces the correct output from its output 0 (if it has one) when unconnected. Generally this is None -
    not Datum of type NONE (i.e. Datum.null). There are exceptions, such as constant and spectrum."""

    pcot.setup()
    for x in XFormType.all():
        doc = Document()            # create document
        node = doc.graph.create(x)  # create the node (there will also be an "input", ignore it).
        doc.graph.performNodes()    # perform all nodes
        if node.getOutputType(0) is not None:   # if the type should have an output
            out = node.getOutput(0)     # get the value
            # most nodes, when unconnected, should output None. There are a few exceptions.
            if x == 'constant':
                try:
                    assert node.getOutput(0, Datum.NUMBER).n == 0, f"Constant should output zero by default"
                except BadTypeException:
                    raise AssertionError("Constant should output a Datum.NUMBER even when not connected")
            elif x == 'spectrum':
                try:
                    assert node.getOutput(0, Datum.DATA) is not None, f"Spectrum should return something always"
                except BadTypeException:
                    pytest.fail("Spectrum should output Datum.DATA even when not connected")
            else:
                assert out is None, f"XForm {x} should output None when not connected"


def test_create_nonexistent_node_type():
    """Try to create a node we know doesn't exist and assert we get a dummy node back."""
    pcot.setup()
    doc = Document()
    node = doc.graph.create("this type does not exist")
    assert node.type.name == 'dummy'


def test_node_defined_after_usage():
    """We define a simple node type below - but can we still create it in a document? If we couldn't, we should
    get a dummy node back from the create"""
    pcot.setup()
    doc = Document()
    node = doc.graph.create("testtype")
    assert node.type.name == 'testtype'


@xformtype
class XFormTest(XFormType):
    """A very simple node - two numeric inputs, two numeric outputs.
    Out0 = in0*val + in1*1000
    Out1 = in1*val + in0*1000"""
    def __init__(self):
        super().__init__("testtype", "processing", "0.0.0")
        self.addInputConnector("", Datum.NUMBER)
        self.addInputConnector("", Datum.NUMBER)
        self.addOutputConnector("", Datum.NUMBER)
        self.addOutputConnector("", Datum.NUMBER)

    def createTab(self, n, w):
        return None

    def init(self, node):
        node.testval = 100

    def perform(self, node):
        in0 = node.getInput(0, Datum.NUMBER)
        in1 = node.getInput(1, Datum.NUMBER)
        if in0 is not None and in1 is not None:
            node.setOutput(0, Datum(Datum.NUMBER, OpData(in0.n*node.testval + in1.n*1000, 0.0), nullSourceSet))
            node.setOutput(1, Datum(Datum.NUMBER, OpData(in1.n*node.testval + in0.n*1000, 0.0), nullSourceSet))
        else:
            node.setOutput(0, None)
            node.setOutput(1, None)


def test_simple_node():
    """Create a simple node, wire it up, and make sure it does the thing it should."""

    # setup, registering the types, and create a document
    pcot.setup()
    doc = Document()
    # create a testtype node and make sure it's OK (i.e. the testtype class above registered OK)
    node = doc.graph.create("testtype")
    assert node.type.name == 'testtype'

    # create two constant nodes set to output 1 and 30.
    const0 = doc.graph.create("constant")
    const0.val = 1
    const1 = doc.graph.create("constant")
    const1.val = 30

    # connect them to the inputs of the testtype node.
    node.connect(0, const0, 0)
    node.connect(1, const1, 0)

    # run the graph
    doc.graph.performNodes()

    # get the outputs and check they are correct.
    out0 = node.getOutput(0, Datum.NUMBER).n
    out1 = node.getOutput(1, Datum.NUMBER).n
    assert out0 == 1*100+30*1000
    assert out1 == 30*100+1*1000
