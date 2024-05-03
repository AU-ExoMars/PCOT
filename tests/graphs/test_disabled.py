import glob
import os

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document


def test_disabled_nodes_run():
    """Test that when we load a graph with disabled nodes, those nodes are run when forced to do so by doc.run().
    This is also tested by the main graph test system, but this is a more focused test."""
    pcot.setup()
    names = glob.glob("**/disabled.pcot", recursive=True)
    if len(names) == 0:
        pytest.fail(f"Could not find disabled.pcot : cwd={os.getcwd()}")

    doc = Document(names[0])
    doc.run()

    # check that the disabled node was run; that all tests pass
    ns = doc.graph.getByDisplayName("sink")
    assert len(ns) == 1
    out = ns[0].data.get(Datum.TESTRESULT)
    if out is None:
        pytest.fail("sink node did not output a test result (node was disabled and did not run when forced to?)")
    assert len(out) == 0

    # check that the expr node was able to run, producing an image
    ns = doc.graph.getByDisplayName("sinkimg")
    assert len(ns) == 1
    out = ns[0].data.get(Datum.IMG)
    if out is None:
        pytest.fail("sinkimg node did not output an image (node was disabled and did not run when forced to?)")


def test_disabled_nodes_dont_run():
    """Test that when we load a graph with disabled nodes, those nodes are NOT run when doc.run() is told not
    to enable disabled nodes"""

    pcot.setup()
    names = glob.glob("**/disabled.pcot", recursive=True)
    if len(names) == 0:
        pytest.fail(f"Could not find disabled.pcot : cwd={os.getcwd()}")

    # this time we run without enabling disabled nodes
    doc = Document(names[0])
    doc.run(forceRunDisabled=False)

    # check that the disabled node was NOT run; that the sink had no input.
    ns = doc.graph.getByDisplayName("sink")
    assert len(ns) == 1
    assert ns[0].data is None

    # check that the expr node was able to run, producing an image
    ns = doc.graph.getByDisplayName("sinkimg")
    assert len(ns) == 1
    assert ns[0].data is None
