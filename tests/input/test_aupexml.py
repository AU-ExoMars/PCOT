"""AUPE XML input tests. These use a real AUPE XML metadata file from tests/data/aupexml, both
directly and as a template for generating files with other exposure times."""
import numpy as np

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.inputs.aupeXMLmethod import AUPEXMLMethod
from fixtures import *

REAL_FILE = "sol00039_00000_00000_00013_LWAC4_T71.0_P-124.0.png.xml"
# the exposure time in that file, exactly as it appears in the ImageMetadata string
REAL_EXPOSURE = "0.009911"


def makeFiles(globaldatadir, directory, exposures):
    """Write copies of the real XML file into a directory, with the exposure time changed.
    exposures is a dict of filename -> exposure time string, or None to remove the
    exposure_time entry entirely (giving a file which can't be read)."""
    template = (globaldatadir / "aupexml" / REAL_FILE).read_text()
    old = f"exposure_time|{REAL_EXPOSURE}|"
    assert old in template
    directory.mkdir(exist_ok=True)
    for name, exp in exposures.items():
        new = "" if exp is None else f"exposure_time|{exp}|"
        (directory / name).write_text(template.replace(old, new))
    return directory


def getMethod(doc, inputidx=0) -> AUPEXMLMethod:
    m = doc.inputMgr.inputs[inputidx].getActive()
    assert isinstance(m, AUPEXMLMethod)
    return m


def test_real_file(globaldatadir):
    """Read the exposure time from a real AUPE XML file, giving a single-element vector
    with one source describing the file."""
    pcot.setup()
    doc = Document()
    directory = globaldatadir / "aupexml"
    assert doc.setInputAUPEXML(0, directory, [REAL_FILE]) is None

    node = doc.graph.create("input 0")
    doc.run()
    d = node.getOutputDatum(0)
    assert d.tp == Datum.NUMBER
    assert d.val.n.shape == (1,)
    assert np.isclose(d.val.n[0], float(REAL_EXPOSURE))
    assert d.val.u[0] == 0
    assert d.val.dq[0] == dq.NOUNCERTAINTY

    assert len(d.sources) == 1
    s = d.sources.getOnlyItem()
    assert s.inputIdx == 0
    assert s.band is None
    assert s.external.brief() == "AUPEXML"
    assert s.external.long() == str((directory / REAL_FILE).resolve())


def test_multiple_files_in_list_order(globaldatadir, tmp_path):
    """The output vector follows the order of the file list, not the alphabetical order of
    the filenames, and has a source for each file."""
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1", "b.xml": "0.02", "c.xml": "0.5"})
    assert doc.setInputAUPEXML(0, directory, ["c.xml", "a.xml", "b.xml"]) is None

    d = getMethod(doc).get()
    assert np.allclose(d.val.n, [0.5, 0.1, 0.02])
    assert np.all(d.val.dq == dq.NOUNCERTAINTY)
    assert len(d.sources) == 3
    assert {s.external.long() for s in d.sources} == {str(directory / f) for f in ["a.xml", "b.xml", "c.xml"]}


def test_unreadable_files_give_nodata(globaldatadir, tmp_path):
    """Files which can't be read (no exposure time, or not XML at all) give NODATA elements
    without affecting the others."""
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1", "noexp.xml": None, "c.xml": "0.5"})
    (directory / "junk.xml").write_text("this is not XML")
    assert doc.setInputAUPEXML(0, directory, ["a.xml", "noexp.xml", "junk.xml", "c.xml"]) is None

    d = getMethod(doc).get()
    assert d.val.n.shape == (4,)
    assert np.allclose(d.val.n[[0, 3]], [0.1, 0.5])
    assert [bool(x & dq.NODATA) for x in d.val.dq] == [False, True, True, False]
    assert len(d.sources) == 4


def test_no_files_gives_null(globaldatadir):
    pcot.setup()
    doc = Document()
    assert doc.setInputAUPEXML(0, globaldatadir / "aupexml", []) is None
    assert getMethod(doc).get().isNone()


def test_save_and_load_preserves_order_and_data(globaldatadir, tmp_path):
    """The file list order and the data survive saving and loading the document"""
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1", "b.xml": "0.02", "c.xml": "0.5"})
    assert doc.setInputAUPEXML(0, directory, ["b.xml", "c.xml", "a.xml"]) is None
    fn = tmp_path / "test.pcot"
    doc.save(str(fn))

    doc2 = Document(str(fn))
    m = getMethod(doc2)
    assert m.dir == directory
    assert m.files == ["b.xml", "c.xml", "a.xml"]
    assert np.allclose(m.get().val.n, [0.02, 0.5, 0.1])
    # and it should be the same when actually re-read from the files
    m.invalidate()
    assert np.allclose(m.get().val.n, [0.02, 0.5, 0.1])


def test_missing_file_keeps_cached_data(globaldatadir, tmp_path):
    """A document opened after one of its files has been deleted reports the missing file
    and keeps the cached data rather than discarding it - unless a reload is forced, in which
    case the missing file's element becomes NODATA."""
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1", "b.xml": "0.02"})
    assert doc.setInputAUPEXML(0, directory, ["a.xml", "b.xml"]) is None
    fn = tmp_path / "test.pcot"
    doc.save(str(fn))
    (directory / "b.xml").unlink()

    m = getMethod(Document(str(fn)))
    reason = m.missingPathReason()
    assert reason is not None
    assert "b.xml" in reason and "using cached data" in reason

    m.invalidate()  # should be a no-op, because the source is missing
    d = m.get()
    assert np.allclose(d.val.n, [0.1, 0.02])
    assert not np.any(d.val.dq & dq.NODATA)

    m.invalidate(force=True)
    d = m.get()
    assert np.isclose(d.val.n[0], 0.1)
    assert [bool(x & dq.NODATA) for x in d.val.dq] == [False, True]


def test_missing_directory(globaldatadir, tmp_path):
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1"})
    assert doc.setInputAUPEXML(0, directory, ["a.xml"]) is None
    m = getMethod(doc)
    assert m.missingPathReason() is None

    (directory / "a.xml").unlink()
    directory.rmdir()
    assert m.missingPathReason().startswith("Directory not found")
    m.invalidate()
    assert np.allclose(m.get().val.n, [0.1])


def test_undo_restores_order(globaldatadir, tmp_path):
    """Reordering the file list in place (as the widget's move buttons do) must not alter the
    stored undo state, so undo restores the previous order."""
    pcot.setup()
    doc = Document()
    directory = makeFiles(globaldatadir, tmp_path / "xml", {"a.xml": "0.1", "b.xml": "0.02"})
    assert doc.setInputAUPEXML(0, directory, ["a.xml", "b.xml"]) is None

    m = getMethod(doc)
    doc.mark()
    m.files[0], m.files[1] = m.files[1], m.files[0]
    assert m.files == ["b.xml", "a.xml"]
    doc.undo()
    assert getMethod(doc).files == ["a.xml", "b.xml"]
    doc.redo()
    assert getMethod(doc).files == ["b.xml", "a.xml"]
