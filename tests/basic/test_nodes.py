import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.xform import XFormType, BadTypeException


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
                    assert node.getOutput(0, Datum.NUMBER) == 0, f"Constant should output zero by default"
                except BadTypeException:
                    raise AssertionError("Constant should output a Datum.NUMBER even when not connected")
            elif x == 'spectrum':
                try:
                    assert node.getOutput(0, Datum.DATA) is not None, f"Spectrum should return something always"
                except BadTypeException:
                    pytest.fail("Spectrum should output Datum.DATA even when not connected")
            else:
                assert out is None, f"XForm {x} should output None when not connected"
