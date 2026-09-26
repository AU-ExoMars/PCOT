"""Tests for reading ancillary data (e.g. exposure time) from sidecar files in multifile inputs.
These use a real AUPE3 sidecar file from tests/data/ancillary as a template, writing copies with
different exposure times next to small generated band images."""
import logging

import cv2 as cv
import numpy as np
import pytest

import pcot
from pcot.ancillary import multifile, keys
from pcot.ancillary.multifile import MultifileSidecarLoader, add_multifile_sidecar_loader
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *

# the exposure time field in the template sidecar, exactly as it appears in the ImageMetadata string
TEMPLATE_EXPOSURE_FIELD = "exposure_time|0.009911|"


@pytest.fixture
def template(globaldatadir):
    text = (globaldatadir / "ancillary" / "aupe3_sidecar.png.xml").read_text()
    assert TEMPLATE_EXPOSURE_FIELD in text
    return text


@pytest.fixture
def restoreLoaders():
    """Restore the registered sidecar loaders after a test which adds some"""
    saved = list(multifile.LOADERS)
    yield
    multifile.LOADERS[:] = saved


def bandName(n):
    """A filename in the real AUPE style, so the default pattern finds filter position L<n>"""
    return f"sol00039_00000_00000_0001{n}_LWAC{n}_T71.0_P-124.0.png"


def makeBand(directory, n, sidecar=None):
    """Write a small band image for filter position L<n>, with the given sidecar text (or no sidecar)"""
    directory.mkdir(exist_ok=True)
    cv.imwrite(str(directory / bandName(n)), np.full((10, 20), n * 10, dtype=np.uint8))
    if sidecar is not None:
        (directory / (bandName(n) + ".xml")).write_text(sidecar)
    return bandName(n)


def withExposure(template, value):
    """The template sidecar with a different exposure time, or with it removed if value is None"""
    return template.replace(TEMPLATE_EXPOSURE_FIELD, "" if value is None else f"exposure_time|{value}|")


def load(directory, files):
    pcot.setup()
    doc = Document()
    assert doc.setInputMulti(0, str(directory), files) is None
    return doc, doc.inputMgr.inputs[0].get().get(Datum.IMG)


def warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_each_band_gets_its_own_sidecar_data(template, tmp_path):
    """Bands get their own sidecar's data, in file-list order; a band with no sidecar has none"""
    d = tmp_path / "bands"
    files = [makeBand(d, 3, withExposure(template, "0.03")),
             makeBand(d, 1, withExposure(template, "0.01")),
             makeBand(d, 2)]
    _, img = load(d, files)
    assert img.ancillary.get(keys.EXPOSURE.name) == [0.03, 0.01, None]


def test_exposure_from_sidecars(template, tmp_path):
    """The whole path: sidecars -> multifile input -> exposure() in an expr node, via band selection"""
    d = tmp_path / "bands"
    files = [makeBand(d, n, withExposure(template, e)) for n, e in [(1, "0.5"), (2, "0.25"), (3, "2")]]
    doc, _ = load(d, files)
    node = doc.graph.create("expr")
    node.connect(0, doc.graph.create("input 0"), 0)
    node.params.expr = "exposure(a)"
    doc.run()
    assert np.allclose(node.getOutput(0, Datum.NUMBER).n, [0.5, 0.25, 2])
    node.params.expr = "exposure(a$530)"      # L2 is 530nm in the PANCAM camera
    doc.run()
    assert np.allclose(node.getOutput(0, Datum.NUMBER).n, [0.25])


def test_real_sidecar_file(template, tmp_path):
    """The template itself is a real AUPE3 sidecar"""
    d = tmp_path / "bands"
    _, img = load(d, [makeBand(d, 4, template)])
    assert img.ancillary.get(keys.EXPOSURE.name) == [0.009911]


def test_unreadable_sidecar_warns(template, tmp_path, caplog):
    """A sidecar no loader can read gives no data for that band and a warning, but the image loads"""
    d = tmp_path / "bands"
    files = [makeBand(d, 1, "this is not XML"),
             makeBand(d, 2, withExposure(template, None)),     # none of the expected fields
             makeBand(d, 3, withExposure(template, "0.03"))]
    _, img = load(d, files)
    assert img.ancillary.get(keys.EXPOSURE.name) == [None, None, 0.03]
    w = warnings(caplog)
    assert any("Could not read ancillary data" in x and bandName(1) in x for x in w)
    assert any("Could not read ancillary data" in x and bandName(2) in x for x in w)


def test_bad_field_value_warns(template, tmp_path, caplog):
    """A recognised sidecar with a bad value for a field leaves that field out, with a warning"""
    d = tmp_path / "bands"
    _, img = load(d, [makeBand(d, 1, withExposure(template, "NULL"))])
    assert img.ancillary.get(keys.EXPOSURE.name) == [None]
    assert any("Bad value for exposure_time" in x for x in warnings(caplog))


def test_missing_sidecar_is_quiet(tmp_path, caplog):
    """No sidecar at all is normal, and mustn't warn"""
    d = tmp_path / "bands"
    _, img = load(d, [makeBand(d, 1)])
    assert img.ancillary.get(keys.EXPOSURE.name) == [None]
    assert not any("ancillary" in x for x in warnings(caplog))


class OtherConvention(MultifileSidecarLoader):
    """A loader for a made-up sidecar convention: a .txt file containing just the exposure"""
    def attempt_load(self, path, problems):
        p = path.with_suffix(".txt")
        if not p.exists():
            return None
        try:
            return {keys.EXPOSURE.name: float(p.read_text())}
        except ValueError as e:
            problems.append(f"OtherConvention could not read {p.name}: {e}")
            return None


def test_other_convention_is_used(template, tmp_path, caplog, restoreLoaders):
    """A band whose sidecar only another loader can read gets that loader's data, without a warning
    from the AUPE3 loader"""
    add_multifile_sidecar_loader(OtherConvention())
    d = tmp_path / "bands"
    files = [makeBand(d, 1, withExposure(template, "0.01")), makeBand(d, 2)]
    (d / bandName(2)).with_suffix(".txt").write_text("0.5")
    _, img = load(d, files)
    assert img.ancillary.get(keys.EXPOSURE.name) == [0.01, 0.5]
    assert not any("ancillary" in x for x in warnings(caplog))


class Overrider(MultifileSidecarLoader):
    """A loader which claims every file, giving a fixed exposure"""
    def attempt_load(self, path, problems):
        return {keys.EXPOSURE.name: 99.0}


def test_loader_order(template, tmp_path, restoreLoaders):
    """Loaders are tried in order and the first to succeed wins: a loader added normally comes after
    the built-in ones, and one added with first=True comes before them"""
    d = tmp_path / "bands"
    files = [makeBand(d, 1, withExposure(template, "0.01"))]

    add_multifile_sidecar_loader(Overrider())
    _, img = load(d, files)
    assert img.ancillary.get(keys.EXPOSURE.name) == [0.01]     # AUPE3 loader still wins

    add_multifile_sidecar_loader(Overrider(), first=True)
    _, img = load(d, files)
    assert img.ancillary.get(keys.EXPOSURE.name) == [99.0]     # overridden
