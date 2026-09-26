"""Tests on per-band ancillary data in ImageCube. The rule is that ancillary data describes how the
pixel data was acquired, so it's kept by operations which don't change pixel values and dropped by
those which do (see internalDocs/docs/ancillary.md)."""
import numpy as np
import pytest

import pcot
from pcot.ancillary.bandancillary import BandAncillary
from pcot.datum import Datum
from pcot.imagecube import ImageCube

pcot.setup()

EXPOSURES = [0.01, 0.02, 0.03]


def makeImage():
    img = np.dstack([np.full((10, 20), v, dtype=np.float32) for v in (1, 2, 3)])
    anc = BandAncillary([{"exposure": e} for e in EXPOSURES])
    return ImageCube(img, ancillary=anc)


def test_default_is_empty():
    img = ImageCube(np.zeros((10, 20, 3), dtype=np.float32))
    assert len(img.ancillary) == 3
    assert img.ancillary.isEmpty()
    assert img.ancillary.get("exposure") == [None, None, None]


def test_wrong_band_count_raises():
    with pytest.raises(Exception):
        ImageCube(np.zeros((10, 20, 3), dtype=np.float32), ancillary=BandAncillary.empty(2))


def test_copies_keep_it_independently():
    img = makeImage()
    for c in [img.copy(), img.shallowCopy()]:
        assert c.ancillary.get("exposure") == EXPOSURES
        # changing the copy's data mustn't change the original's
        c.ancillary[0]["exposure"] = 99
        assert img.ancillary.get("exposure") == EXPOSURES


def test_geometric_operations_keep_it():
    img = makeImage()
    assert img.rotate(90).ancillary.get("exposure") == EXPOSURES
    assert img.flip().ancillary.get("exposure") == EXPOSURES


def test_changing_pixels_drops_it():
    img = makeImage()
    sub = img.subimage()
    assert img.modifyWithSub(sub, sub.img * 2).ancillary.isEmpty()
    assert img.zeros_like().ancillary.isEmpty()


def test_changing_only_dq_keeps_it():
    img = makeImage()
    sub = img.subimage()
    out = img.modifyWithSub(sub, None, dqOR=pcot.dq.SAT, uncertainty=sub.uncertainty)
    assert out.ancillary.get("exposure") == EXPOSURES


def test_arithmetic_drops_it():
    """e.g. the result of a/exposure(a) mustn't still claim to have the original exposure"""
    d = Datum(Datum.IMG, makeImage()) * Datum.k(2)
    assert d.get(Datum.IMG).ancillary.isEmpty()


def test_select_and_concat():
    anc = makeImage().ancillary
    assert anc.select([2, 0]).get("exposure") == [0.03, 0.01]
    both = BandAncillary.concat([anc, BandAncillary.empty(2)])
    assert both.get("exposure") == EXPOSURES + [None, None]


def test_serialise_roundtrip():
    d = makeImage().serialise()
    assert ImageCube.deserialise(d).ancillary.get("exposure") == EXPOSURES


def test_legacy_data_without_ancillary_loads():
    """Images saved before ancillary data existed load with empty ancillary data"""
    d = makeImage().serialise()
    del d['ancillary']
    img = ImageCube.deserialise(d)
    assert len(img.ancillary) == 3
    assert img.ancillary.isEmpty()


def test_document_save_and_load(tmp_path):
    """Ancillary data survives a real save and load, through the archive's JSON"""
    from pcot.document import Document
    doc = Document()
    doc.setInputDirectImage(0, makeImage())
    fn = tmp_path / "test.pcot"
    doc.save(str(fn))
    img = Document(str(fn)).inputMgr.inputs[0].get().get(Datum.IMG)
    assert img.ancillary.get("exposure") == EXPOSURES


def test_non_json_values_fail_to_save(tmp_path):
    """Ancillary values must be JSON-serialisable: anything else fails loudly when saving"""
    from pcot.document import Document
    from pcot.utils.archive import NotJSONSerializable
    img = makeImage()
    img.ancillary[0]["exposure"] = np.float32(0.01)
    doc = Document()
    doc.setInputDirectImage(0, img)
    with pytest.raises(NotJSONSerializable):
        doc.save(str(tmp_path / "test.pcot"))


def runExpr(cube, expr):
    """Run an expr node on an image in input 0, returning the node"""
    from pcot.document import Document
    doc = Document()
    doc.setInputDirectImage(0, cube)
    node = doc.graph.create("expr")
    node.connect(0, doc.graph.create("input 0"), 0)
    node.params.expr = expr
    doc.run()
    return node


def test_exposure_function():
    """exposure() gives a vector of per-band exposures, with no uncertainty"""
    e = pcot.datumfuncs.exposure(Datum(Datum.IMG, makeImage()))
    assert e.tp == Datum.NUMBER
    assert np.allclose(e.val.n, EXPOSURES)
    assert np.all(e.val.u == 0)
    assert np.all(e.val.dq == pcot.dq.NOUNCERTAINTY)


def test_normalise_by_exposure():
    """a/exposure(a) divides each band by its own exposure (the image has values 1, 2, 3)"""
    node = runExpr(makeImage(), "a/exposure(a)")
    assert node.error is None
    out = node.getOutput(0, Datum.IMG)
    assert np.allclose(out.img[0, 0], [1 / 0.01, 2 / 0.02, 3 / 0.03])
    assert out.ancillary.isEmpty()   # so it can't be normalised twice by accident


def test_normalise_single_band():
    cube = ImageCube(np.full((10, 20), 3, dtype=np.float32), ancillary=BandAncillary([{"exposure": 0.5}]))
    node = runExpr(cube, "a/exposure(a)")
    assert node.error is None
    assert np.allclose(node.getOutput(0, Datum.IMG).img, 6)


def test_exposure_missing_gives_clear_error():
    """A clear error, naming the bands, rather than a confusing one from the operator"""
    cube = makeImage()
    del cube.ancillary[1]["exposure"]
    node = runExpr(cube, "a/exposure(a)")
    assert node.error is not None
    assert "no exposure data for band(s) 1" in node.error.message

    node = runExpr(ImageCube(np.zeros((10, 20, 3), dtype=np.float32)), "a/exposure(a)")
    assert "the image has no exposure data" in node.error.message

    # and it's gone after an operation which changes pixel values
    node = runExpr(makeImage(), "exposure(a*2)")
    assert "the image has no exposure data" in node.error.message


def makeFilteredImage():
    """As makeImage(), but with filters on the bands: 440, 540, 640nm"""
    from pcot.cameras.filters import Filter
    from pcot.sources import MultiBandSource, Source
    img = makeImage()
    img.sources = MultiBandSource([
        Source().setBand(Filter(cwl=c, fwhm=20, transmission=1, position=f"P{i}", name=f"F{c}")).setInputIdx(0)
        for i, c in enumerate([440, 540, 640])])
    return img


def exposureOf(cube, expr):
    """Run exposure(expr) in an expr node on an image in input 0"""
    node = runExpr(cube, f"exposure({expr})")
    assert node.error is None, node.error.message
    return list(node.getOutput(0, Datum.NUMBER).n)


def test_band_selection_keeps_it():
    cube = makeFilteredImage()
    assert np.allclose(exposureOf(cube, "a$640"), [0.03])     # by wavelength
    assert np.allclose(exposureOf(cube, "a$F540"), [0.02])    # by name
    assert np.allclose(exposureOf(cube, "a$0"), [0.01])       # by index


def test_rgb_keeps_it_for_mapped_bands():
    img = makeFilteredImage()
    img.mapping.set(2, 0, 1)
    assert img.rgbImage().ancillary.get("exposure") == [0.03, 0.01, 0.02]


def test_crops_and_resize_keep_it():
    from pcot.rois import ROIRect
    img = makeImage()
    img.rois = [ROIRect(rect=(2, 2, 5, 5))]
    assert img.cropROI().ancillary.get("exposure") == EXPOSURES
    assert img.subimage().cropother(img).ancillary.get("exposure") == EXPOSURES
    assert img.resize(40, 20, 1).ancillary.get("exposure") == EXPOSURES
    assert np.allclose(exposureOf(makeImage(), "crop(a,0,0,5,5)"), EXPOSURES)


def test_merge_concatenates_it():
    cube = makeFilteredImage()
    assert np.allclose(exposureOf(cube, "merge(a$640, a$440)"), [0.03, 0.01])
    # a number becomes a band with no ancillary data
    merged = pcot.datumfuncs.merge(Datum(Datum.IMG, cube), Datum.k(2)).get(Datum.IMG)
    assert merged.ancillary.get("exposure") == EXPOSURES + [None]


def runNode(typename, images, setup=None):
    """Run a node of the given type, with each image in a direct input connected to its inputs in
    order. 'setup' is an optional function called on the node before running."""
    from pcot.document import Document
    doc = Document()
    node = doc.graph.create(typename)
    for i, cube in enumerate(images):
        doc.setInputDirectImage(i, cube)
        node.connect(i, doc.graph.create(f"input {i}"), 0)
    if setup is not None:
        setup(node)
    doc.run()
    assert node.error is None, node.error.message
    return node


def test_nominal_keeps_it():
    """nominal() only strips the uncertainty"""
    assert np.allclose(exposureOf(makeImage(), "nominal(a)"), EXPOSURES)


def test_offset_node_keeps_it():
    def setup(node):
        node.params.x, node.params.y = 2, 1
    node = runNode("offset", [makeImage()], setup)
    assert node.getOutput(0, Datum.IMG).ancillary.get("exposure") == EXPOSURES


def test_autoregister_keeps_moving_images_data():
    other = makeImage()
    for d, e in zip(other.ancillary.bands, [1, 2, 3]):
        d["exposure"] = e
    node = runNode("tvl1 autoreg", [makeImage(), other])
    assert node.getOutput(0, Datum.IMG).ancillary.get("exposure") == EXPOSURES


def test_manualregister_keeps_both_images_data():
    other = makeImage()
    for d, e in zip(other.ancillary.bands, [1, 2, 3]):
        d["exposure"] = e

    def setup(node):
        node.params.translate = True
        node.moving = [(5, 5)]
        node.fixed = [(6, 4)]
    node = runNode("manual register", [makeImage(), other], setup)
    assert node.getOutput(0, Datum.IMG).ancillary.get("exposure") == EXPOSURES   # moving
    assert node.getOutput(1, Datum.IMG).ancillary.get("exposure") == [1, 2, 3]   # fixed
