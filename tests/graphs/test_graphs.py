"""This package runs a set of tests which come from graph files. There should be a set of .pcot files, which
must contain graphs which (eventually) output TESTRESULT data to sink nodes. The system will automatically run
these graphs and check the results. Normally, the sinks must contain zero failures. If the graph's filename
contains MUSTFAIL then there must be at least one failure (this is to test the test system itself)."""

import inspect
import logging
import os
from os import getcwd

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document

logger = logging.Logger(__name__)

currentFile = inspect.getfile(inspect.currentframe())
currentDir = os.path.dirname(currentFile)
logger.info(f"Getting graphs for testing from {currentDir}")

# get all the .pcot files in the same dir as this module
graphs = []
for root, dirs, files in os.walk(currentDir):
    for f in [x for x in files if x.lower().endswith(".pcot")]:
        graphs.append(os.path.join(root, f))


def test_graph_file_count():
    """Make sure we got some tests which we know exist"""
    got1 = False
    got2 = False
    for x in graphs:
        if "norm.pcot" in x:
            got1 = True
        if "norm_mustfail.pcot" in x:
            got2 = True
    assert got1
    assert got2


@pytest.mark.parametrize("graphname", graphs)
def test_graph_files(graphname):
    """Takes a relative graph file name. Loads and runs the graph. Finds a sink nodes and reads their output; it should
    be a TESTRESULT of zero failures. Graphs with MUSTFAIL in the name must have more than one failure, however.
    """

    logger.info(f"Running graph {graphname}")
    pcot.setup()
    doc = Document(graphname)
    doc.changed()

    commentFound = False

    comments = doc.graph.getByDisplayName("comment")
    for n in comments:
        if n.string.startswith("DOC"):
            commentFound = True

    if not commentFound:
        pytest.fail("Graph tests require a comment that starts with DOC for documentation")

    ns = doc.graph.getByDisplayName("sink")
    foundOne = False    # we must find at least one sink that outputs a test result
    if len(ns) == 0:
        pytest.fail("cannot find sink")
    for n in ns:
        res = n.out.get(Datum.TESTRESULT)
        logger.info(f"Found a sink, output is {res}")
        if res is not None:
            foundOne = True
            if "mustfail" in graphname.lower():
                assert len(res) > 0
            else:
                assert len(res) == 0

    if not foundOne:
        pytest.fail("cannot find a sink with test result output")
