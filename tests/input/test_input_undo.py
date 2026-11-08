"""Undo/redo of changes to an input's settings should restore the data that goes with the settings,
without reading any files - so it also works when the original files are missing."""
import os
import shutil

import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *


def _inputShape(doc):
    """Shape of the image from the doc's "input 0" node. Undo replaces the nodes, so find it each time."""
    node = [n for n in doc.graph.nodes if n.type.name == "input 0"][0]
    return node.getOutput(0, Datum.IMG).img.shape


def _undo(doc):
    doc.undo()
    doc.graph.changed(runAll=True, invalidateInputs=False)  # as the main window does after an undo


def _redo(doc):
    doc.redo()
    doc.graph.changed(runAll=True, invalidateInputs=False)


def _changeFile(doc, fname):
    """Change the RGB input's file as the UI would: mark, change, invalidate, run"""
    m = doc.inputMgr.inputs[0].getActive()
    doc.mark()
    m.fname = fname
    m.invalidate()
    doc.run()


def test_undo_input_file_change(globaldatadir):
    """Undoing a change of an input's file restores the old file's data, and redo restores the new"""
    pcot.setup()
    doc = Document()
    doc.setInputRGB(0, str(globaldatadir / "basn2c16.png"))     # 32x32
    doc.graph.create("input 0")
    doc.run()
    assert _inputShape(doc) == (32, 32, 3)

    _changeFile(doc, str(globaldatadir / "rect1.png"))          # 40x30
    assert _inputShape(doc) == (30, 40, 3)

    _undo(doc)
    assert doc.inputMgr.inputs[0].getActive().fname == str(globaldatadir / "basn2c16.png")
    assert _inputShape(doc) == (32, 32, 3)

    _redo(doc)
    assert doc.inputMgr.inputs[0].getActive().fname == str(globaldatadir / "rect1.png")
    assert _inputShape(doc) == (30, 40, 3)


def test_undo_input_file_change_original_missing(globaldatadir, tmp_path):
    """The common case of a document opened without its original files: the input uses the data cached
    in the document. Changing to another file and undoing should restore the cached data, even though
    the original file can't be read."""
    pcot.setup()
    orig = tmp_path / "orig.png"
    shutil.copy(globaldatadir / "basn2c16.png", orig)
    doc = Document()
    doc.setInputRGB(0, str(orig))
    doc.graph.create("input 0")
    doc.run()
    docfile = tmp_path / "doc.pcot"
    doc.save(str(docfile))
    os.remove(orig)

    doc = Document(str(docfile))
    doc.run()
    assert doc.inputMgr.inputs[0].getActive().missingPathReason() is not None
    assert _inputShape(doc) == (32, 32, 3)      # from the data cached in the document

    _changeFile(doc, str(globaldatadir / "rect1.png"))
    assert _inputShape(doc) == (30, 40, 3)

    _undo(doc)
    assert _inputShape(doc) == (32, 32, 3)


def test_undo_node_change_keeps_input_data(globaldatadir):
    """Undoing a change which doesn't involve the input keeps the same cached data object"""
    pcot.setup()
    doc = Document()
    doc.setInputRGB(0, str(globaldatadir / "basn2c16.png"))
    doc.graph.create("input 0")
    doc.run()
    m = doc.inputMgr.inputs[0].getActive()
    cached = m.data
    doc.mark()
    doc.graph.create("expr")
    doc.undo()
    assert m.data is cached
