"""Tests for nodes which use complex TaggedAggregate serialisation (CTAS), where the node data is rebuilt
from node.params by nodeDataFromParams()."""

import numpy as np

from pcot.datum import Datum
from pcot.document import Document
from pcot.imagecube import ImageCube


def test_new_stitch_node_survives_node_data_from_params():
    """A newly created stitch node's params should agree with its data, so rebuilding the data from the params
    (as a script would after editing the params of some node) doesn't leave it with no offsets."""
    doc = Document()
    doc.setInputDirectImage(0, ImageCube(np.zeros((10, 10, 3), dtype=np.float32)))
    node = doc.graph.create("stitch")
    node.connect(0, doc.graph.create("input 0"), 0)
    offsets = list(node.offsets)
    order = list(node.order)

    doc.graph.nodeDataFromParams()
    assert node.offsets == offsets
    assert node.order == order

    doc.run()
    assert node.getOutput(0, Datum.IMG) is not None


def test_colourmap_preset_is_copied():
    """Setting a colourmap's gradient from a preset should copy the preset, so changing the node's gradient
    doesn't change the preset."""
    from pcot.xforms.xformcolourmap import presetGradients

    doc = Document()
    node = doc.graph.create("colourmap")
    original = list(presetGradients["magma"].data)
    node.params.preset = "magma"
    doc.graph.nodeDataFromParams()
    assert node.gradient is not presetGradients["magma"]

    node.gradient.setData([(0, (0, 0, 1)), (1, (1, 0, 0))])
    assert presetGradients["magma"].data == original
