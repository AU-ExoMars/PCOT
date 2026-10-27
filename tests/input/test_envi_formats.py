"""Tests of loading the different ENVI formats: data types, interleaves, byte orders, header offsets,
gains and offsets, ignore values and missing optional fields"""

import numpy as np
import pytest

import pcot
from pcot import dq
from pcot.ancillary import keys
from pcot.datum import Datum
from pcot.dataformats import load
from gen_envi import gen_envi_raw

pcot.setup()


def makeData():
    """a 3x4 image with 2 bands, every value different so that any mixup of axes shows"""
    return np.arange(3 * 4 * 2).reshape(3, 4, 2)


def loadRaw(tmp_path, data=None, apply_gains_and_offsets=False, **kwargs):
    """write an ENVI with gen_envi_raw and load it back, returning the ImageCube"""
    data = makeData() if data is None else data
    fn = tmp_path / "test"
    gen_envi_raw(fn, data, **kwargs)
    return load.envi(fn.with_suffix(".hdr"), apply_gains_and_offsets=apply_gains_and_offsets).get(Datum.IMG)


@pytest.mark.parametrize("interleave", ["bsq", "bil", "bip"])
def test_interleaves(tmp_path, interleave):
    """All three interleaves give the same image"""
    img = loadRaw(tmp_path, interleave=interleave)
    assert img.img.dtype == np.float32
    assert np.array_equal(img.img, makeData())


@pytest.mark.parametrize("dtype", [np.uint8, np.int16, np.int32, np.float32, np.float64,
                                   np.uint16, np.uint32, np.int64, np.uint64])
@pytest.mark.parametrize("byteorder", [0, 1])
def test_datatypes_and_byteorders(tmp_path, dtype, byteorder):
    """Every supported data type in both byte orders loads as the same float32 image"""
    img = loadRaw(tmp_path, dtype=dtype, byteorder=byteorder)
    assert img.img.dtype == np.float32
    assert np.array_equal(img.img, makeData())


def test_big_endian_bil(tmp_path):
    """Byte order and interleave together"""
    img = loadRaw(tmp_path, dtype=np.uint16, byteorder=1, interleave="bil")
    assert np.array_equal(img.img, makeData())


def test_header_offset(tmp_path):
    """Junk bytes at the start of the data file are skipped"""
    img = loadRaw(tmp_path, dtype=np.int16, header_offset=17)
    assert np.array_equal(img.img, makeData())


def test_wrong_size(tmp_path):
    fn = tmp_path / "test"
    gen_envi_raw(fn, makeData(), dtype=np.uint16)
    with open(fn.with_suffix(".dat"), "ab") as f:
        f.write(b"\0\0")
    with pytest.raises(Exception, match="Size of ENVI data file is incorrect"):
        load.envi(fn.with_suffix(".hdr"))


@pytest.mark.parametrize("extra, msg", [
    ("data gain values = {1, 2, 3}\n", "3 data gain values but 2 bands"),
    ("data offset values = {1}\n", "1 data offset values but 2 bands"),
    ("exposure times = {1, 2, 3}\n", "3 exposure times but 2 bands"),
])
def test_wrong_length_lists(tmp_path, extra, msg):
    with pytest.raises(Exception, match=msg):
        loadRaw(tmp_path, extra=extra)


def test_bad_interleave(tmp_path):
    with pytest.raises(Exception, match="Unknown interleave"):
        loadRaw(tmp_path, interleave="foo")


def test_bad_datatype(tmp_path):
    fn = tmp_path / "test"
    gen_envi_raw(fn, makeData())
    hdr = fn.with_suffix(".hdr")
    hdr.write_text(hdr.read_text().replace("data type = 4", "data type = 6"))
    with pytest.raises(Exception, match="Unknown data type"):
        load.envi(hdr)


GAINS_OFFSETS = "data gain values = {2, 3}\ndata offset values = {10, 20}\n"


def test_gains_and_offsets(tmp_path):
    """Gains and offsets are applied as gain*value+offset, and stored as ancillary data"""
    img = loadRaw(tmp_path, dtype=np.uint16, extra=GAINS_OFFSETS, apply_gains_and_offsets=True)
    data = makeData()
    assert np.allclose(img.img[:, :, 0], data[:, :, 0] * 2 + 10)
    assert np.allclose(img.img[:, :, 1], data[:, :, 1] * 3 + 20)
    assert img.ancillary.get(keys.GAIN.name) == [2, 3]
    assert img.ancillary.get(keys.OFFSET.name) == [10, 20]


def test_offsets_without_gains(tmp_path):
    img = loadRaw(tmp_path, extra="data offset values = {10, 20}\n", apply_gains_and_offsets=True)
    assert np.allclose(img.img, makeData() + [10, 20])
    assert img.ancillary.get(keys.GAIN.name) == [None, None]


def test_gains_and_offsets_not_applied_by_default(tmp_path):
    """Unless we ask for them to be applied the raw data comes through, but they are still in the ancillary"""
    fn = tmp_path / "test"
    gen_envi_raw(fn, makeData(), extra=GAINS_OFFSETS)
    img = load.envi(fn.with_suffix(".hdr")).get(Datum.IMG)
    assert np.array_equal(img.img, makeData())
    assert img.ancillary.get(keys.GAIN.name) == [2, 3]


def test_ignore_value(tmp_path):
    """Pixels matching the ignore value in the raw data are NODATA, even with a gain"""
    data = makeData()
    data[1, 2, 1] = 1000
    img = loadRaw(tmp_path, data=data, dtype=np.uint16, byteorder=1, interleave="bil",
                  extra="data ignore value = 1000\ndata gain values = {2, 2}\n", apply_gains_and_offsets=True)
    expected = np.zeros(data.shape, dtype=np.uint16)
    expected[1, 2, 1] = dq.NODATA
    assert np.array_equal(img.dq & dq.NODATA, expected)


def test_ignore_value_nan(tmp_path):
    data = makeData().astype(np.float32)
    data[0, 0, 0] = np.nan
    img = loadRaw(tmp_path, data=data, extra="data ignore value = NaN\n")
    nodata = img.dq & dq.NODATA
    assert nodata[0, 0, 0]
    assert np.count_nonzero(nodata) == 1


def test_no_ignore_value(tmp_path):
    img = loadRaw(tmp_path)
    assert not np.any(img.dq & dq.NODATA)


def test_minimal_header(tmp_path):
    """No wavelengths, band names, exposures or gains: we get dummy filters and no ancillary data
    (in particular no made-up exposures)"""
    img = loadRaw(tmp_path)
    names = [ss.getOnlyItem().getFilter().name for ss in img.sources]
    assert names == ["band 0", "band 1"]
    assert img.ancillary.isEmpty()


def test_band_names_without_wavelengths(tmp_path):
    img = loadRaw(tmp_path, extra="band names = {red, green}\n")
    names = [ss.getOnlyItem().getFilter().name for ss in img.sources]
    assert names == ["red", "green"]


def test_exposure_times(tmp_path):
    img = loadRaw(tmp_path, extra="exposure times = {0.5, 0.25}\n")
    assert img.ancillary.get(keys.EXPOSURE.name) == [0.5, 0.25]


def test_write_has_no_ignore_value(tmp_path):
    """Images PCOT writes as ENVI don't get an ignore value, so no pixel value comes back as NODATA"""
    from pcot.dataformats import envi
    from pcot.imagecube import ImageCube
    from pcot.cameras.filters import Filter
    from pcot.sources import MultiBandSource, Source

    data = makeData().astype(np.float32)
    data[0, 0, 0] = 241     # the ignore value we used to write
    sources = MultiBandSource([Source().setBand(Filter(cwl=c, fwhm=10)) for c in (440, 540)])
    envi.write(str(tmp_path / "out"), ImageCube(data, sources=sources))
    img = load.envi(tmp_path / "out.hdr").get(Datum.IMG)
    assert np.array_equal(img.img, data)
    assert not np.any(img.dq & dq.NODATA)


def runParams(doc, params):
    from pcot.parameters.inputs import processParameterFileForInputsTest
    from pcot.parameters.parameterfile import ParameterFile
    processParameterFileForInputsTest(doc, ParameterFile().parse(params))
    doc.run()
    return doc.graph.getByDisplayName("input 0", True).getOutput(0, Datum.IMG)


def makeGainsFile(tmp_path):
    fn = tmp_path / "test"
    gen_envi_raw(fn, makeData(), extra=GAINS_OFFSETS)
    return fn.with_suffix(".hdr")


def test_apply_gains_parameter_and_serialisation(tmp_path):
    """The apply_gains_and_offsets setting can be set from a parameter file and survives save/load"""
    from pcot.document import Document

    hdr = makeGainsFile(tmp_path)
    doc = Document()
    img = runParams(doc, f"""
    inputs.0.envi.filename = {hdr}
    inputs.0.envi.apply_gains_and_offsets = y
    """)
    assert not np.array_equal(img.img, makeData())

    doc.save(str(tmp_path / "test.pcot"))
    doc = Document(tmp_path / "test.pcot")
    assert doc.inputMgr.inputs[0].getActive().apply_gains_and_offsets is True


def test_apply_gains_parameter_alone(tmp_path):
    """Setting just the flag changes an existing ENVI input, and reloads it"""
    from pcot.document import Document

    doc = Document()
    img = runParams(doc, f"inputs.0.envi.filename = {makeGainsFile(tmp_path)}")
    assert np.array_equal(img.img, makeData())     # gains not applied by default
    img = runParams(doc, "inputs.0.envi.apply_gains_and_offsets = y")
    assert not np.array_equal(img.img, makeData())
    img = runParams(doc, "inputs.0.envi.apply_gains_and_offsets = n")
    assert np.array_equal(img.img, makeData())


def test_filename_parameter_keeps_document_setting(tmp_path):
    """Setting just the filename doesn't reset a document's apply_gains_and_offsets setting"""
    from pcot.document import Document

    hdr = makeGainsFile(tmp_path)
    doc = Document()
    runParams(doc, f"""
    inputs.0.envi.filename = {hdr}
    inputs.0.envi.apply_gains_and_offsets = y
    """)
    img = runParams(doc, f"inputs.0.envi.filename = {hdr}")
    assert not np.array_equal(img.img, makeData())


def test_set_input_envi_gains(tmp_path):
    """setInputENVI can set apply_gains_and_offsets, and keeps the existing setting if it isn't given"""
    from pcot.document import Document

    hdr = makeGainsFile(tmp_path)
    doc = Document()
    node = doc.graph.create("input 0")

    def run():
        doc.run()
        return node.getOutput(0, Datum.IMG)

    assert doc.setInputENVI(0, hdr) is None
    assert np.array_equal(run().img, makeData())     # off by default
    assert doc.setInputENVI(0, hdr, apply_gains_and_offsets=True) is None
    assert not np.array_equal(run().img, makeData())
    assert doc.setInputENVI(0, hdr) is None
    assert not np.array_equal(run().img, makeData())     # setting kept
    assert doc.setInputENVI(0, hdr, apply_gains_and_offsets=False) is None
    assert np.array_equal(run().img, makeData())


def test_apply_gains_parameter_alone_not_envi(tmp_path):
    """Setting just the flag on an input which isn't ENVI is an error, rather than being ignored"""
    from pcot.document import Document

    with pytest.raises(Exception, match="no envi.filename given"):
        runParams(Document(), "inputs.0.envi.apply_gains_and_offsets = n")
