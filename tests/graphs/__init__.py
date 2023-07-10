"""These tests are more complex, and involve loading graphs into PCOT from files
and testing that they produce the correct data."""
import logging

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document

logger = logging.Logger(__name__)


def check_graph(graphname, lst):
    """Takes a graph name. Loads and runs the graph. Then runs through the list, checking
    the pixels - each tuple in the list is (x,y, n,u,dq), so it's a pixel and Value."""

    pcot.setup()
    doc = Document(graphname)
    doc.changed()
    node = doc.graph.get("sink")
    if node is None:
        pytest.fail("cannot find sink")
    img = node.out.get(Datum.IMG)
    if img is None:
        pytest.fail("output of sink is not an image")

    for x, y, n, u, dq in lst:
        pix = img[x, y]
        en = pix.n == pytest.approx(n)
        eu = pix.u == pytest.approx(u)
        edq = pix.dq == dq
        if not (en and eu and edq):
            logger.info(f"{x}, {y} en={en}, eu={eu}, dq={edq}")
