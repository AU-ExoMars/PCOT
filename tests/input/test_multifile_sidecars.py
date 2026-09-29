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

# the exposure time and filter number fields in the template sidecar, exactly as they appear in the
# ImageMetadata string, and its camera (which gives the lens)
TEMPLATE_EXPOSURE_FIELD = "exposure_time|0.009911|"
TEMPLATE_FILTER_FIELD = "filter_num|4|"
TEMPLATE_CAMERA = "Camera=WAC_LEFT;"


@pytest.fixture
def template(globaldatadir):
    text = (globaldatadir / "ancillary" / "aupe3_sidecar.png.xml").read_text()
    assert TEMPLATE_EXPOSURE_FIELD in text
    assert TEMPLATE_FILTER_FIELD in text
    assert TEMPLATE_CAMERA in text
    return text


@pytest.fixture
def restoreLoaders():
    """Restore the registered sidecar loaders after a test which adds some"""
    saved = list(multifile.LOADERS)
    yield
    multifile.LOADERS[:] = saved


def bandName(n):
    """A filename in the real AUPE style, so the default pattern finds filter position L<n>"""
    return f"sol00039_00000_00000_0001{n}_L{n:02d}_T71.0_P-124.0.png"


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


def withFilter(template, n, camera="WAC_LEFT"):
    """The template sidecar with a different filter number (or none if n is None) and camera"""
    text = template.replace(TEMPLATE_FILTER_FIELD, "" if n is None else f"filter_num|{n}|")
    return text.replace(TEMPLATE_CAMERA, f"Camera={camera};")


def load(directory, files, filterpat=None, camera=None):
    pcot.setup()
    doc = Document()
    assert doc.setInputMulti(0, str(directory), files, filterpat=filterpat, camera=camera) is None
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
    """The whole path: sidecars -> multifile input -> exposure() in an expr node, via band selection.
    PANCAM has separate L/R lenses, so filter positions are e.g. "L02" - we need lens+n groups
    in the filter pattern (rather than relying on the ambient default_camera/multifile_pattern
    settings from the user's own config, which won't necessarily compose positions this way) to
    reliably resolve wavelengths regardless of the machine running the test."""
    d = tmp_path / "bands"
    files = [makeBand(d, n, withExposure(template, e)) for n, e in [(1, "0.5"), (2, "0.25"), (3, "2")]]
    doc, _ = load(d, files, filterpat=r".*(?P<lens>[LR])(?P<n>[0-9][0-9]).*", camera="PANCAM")
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
             makeBand(d, 2, withFilter(withExposure(template, None), None)),     # none of the expected fields
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


# a filter pattern for positions like "L04" in filenames - which the "capture" files below don't match
LENS_PATTERN = r".*(?P<lens>[LR])(?P<n>[0-9][0-9]).*"


def makePlainBand(directory, k, sidecar=None):
    """Write a small band image whose filename says nothing about its filter, with the given sidecar"""
    directory.mkdir(exist_ok=True)
    name = f"capture{k}.png"
    cv.imwrite(str(directory / name), np.full((10, 20), k * 10, dtype=np.uint8))
    if sidecar is not None:
        (directory / (name + ".xml")).write_text(sidecar)
    return name


def bandFilters(img):
    return [ss.getOnlyItem().getFilter() for ss in img.sources]


def errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_sidecar_filter_data(template, tmp_path):
    """The AUPE3 loader reads the filter number, and the lens from the camera name"""
    d = tmp_path / "bands"
    files = [makeBand(d, 1, withFilter(template, 4)),
             makeBand(d, 2, withFilter(template, 7, "WAC_RIGHT")),
             makeBand(d, 3, withFilter(template, 2, "HRC")),       # no lens for this camera
             makeBand(d, 5, withFilter(template, None))]           # no filter number
    _, img = load(d, files, filterpat=LENS_PATTERN, camera="PANCAM")
    assert img.ancillary.get(keys.FILTER_NUMBER.name) == [4, 7, 2, None]
    assert img.ancillary.get(keys.LENS.name) == ['L', 'R', None, 'L']


def test_filter_from_sidecar_lens_positions(template, tmp_path, caplog):
    """When the filename doesn't give the filter, the sidecar's lens and filter number are used - here
    for a camera whose positions include the lens (e.g. "L04"). No errors are reported."""
    from pcot.cameras import getFilter
    d = tmp_path / "bands"
    files = [makePlainBand(d, 1, withFilter(template, 4)),
             makePlainBand(d, 2, withFilter(template, 2, "WAC_RIGHT"))]
    _, img = load(d, files, filterpat=LENS_PATTERN, camera="PANCAM")
    assert bandFilters(img) == [getFilter("PANCAM", "L04", 'pos'), getFilter("PANCAM", "R02", 'pos')]
    assert errors(caplog) == []


def test_filter_from_sidecar_numbered_positions(template, tmp_path, caplog):
    """As above, for a camera whose positions are just numbers (e.g. "04"): the lens is dropped"""
    from pcot.cameras import getFilter
    d = tmp_path / "bands"
    _, img = load(d, [makePlainBand(d, 1, withFilter(template, 4))],
                  filterpat=LENS_PATTERN, camera="AUPE_LEFT_NOCALIB")
    assert bandFilters(img) == [getFilter("AUPE_LEFT_NOCALIB", "04", 'pos')]
    assert errors(caplog) == []


def test_filename_filter_wins_with_warning(template, tmp_path, caplog):
    """If the filename and sidecar disagree about the filter, the filename wins, with a warning"""
    from pcot.cameras import getFilter
    d = tmp_path / "bands"
    _, img = load(d, [makeBand(d, 1, withFilter(template, 3))], filterpat=LENS_PATTERN, camera="PANCAM")
    assert bandFilters(img) == [getFilter("PANCAM", "L01", 'pos')]
    assert any("using the filename" in x and bandName(1) in x for x in warnings(caplog))


def test_filename_and_sidecar_agree_quietly(template, tmp_path, caplog):
    """No warning if the filename and sidecar give the same filter"""
    d = tmp_path / "bands"
    load(d, [makeBand(d, 4, withFilter(template, 4))], filterpat=LENS_PATTERN, camera="PANCAM")
    assert not any("using the filename" in x for x in warnings(caplog))


def test_no_filter_is_an_error(template, tmp_path, caplog):
    """If neither the filename nor the sidecar gives a filter, an error explains why and the band
    gets the dummy filter"""
    from pcot.cameras.filters import DUMMY_FILTER
    d = tmp_path / "bands"
    files = [makePlainBand(d, 1, withFilter(template, None)),      # no filter number
             makePlainBand(d, 2, withFilter(template, 99))]        # filter number not in the camera
    _, img = load(d, files, filterpat=LENS_PATTERN, camera="PANCAM")
    assert bandFilters(img) == [DUMMY_FILTER, DUMMY_FILTER]
    e = errors(caplog)
    assert any("cannot find the filter" in x and "capture1.png" in x and "no filter number" in x for x in e)
    assert any("cannot find the filter" in x and "capture2.png" in x and "L99 isn't in the camera" in x for x in e)
