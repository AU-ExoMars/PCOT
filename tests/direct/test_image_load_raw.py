"""
Tests for loading raw files.
"""

import os
import struct
import tempfile

import numpy as np

import pcot
from pcot import dq
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.datum import Datum
from pcot.value import Value


def create_raw_uint16(dir, fn, offset=0, bigendian=False, width=16, height=32, fill=None):
    """Create a 16-bit raw image file, 16x32, optional header offset. Fill is a list of (x,y,val) triples
    to write."""

    # create black mono image, 16x32 - coords are y,x because we're row-major
    img = np.zeros((height, width), dtype=np.uint16)

    if fill is not None:
        for x, y, v in fill:
            img[y, x] = v

    fn = os.path.join(dir, fn)

    # write it out
    with open(fn, "wb") as f:
        # first write out a header of "offset" bytes, each of which is 10 (just to make it a bit more interesting)
        f.write(b'\x0A' * offset)
        for i in range(height):
            endianness = ">" if bigendian else "<"
            f.write(struct.pack(f"{endianness}{width}H", *img[i]))


def create_raw_float32(dir, fn, offset=0, bigendian=False, width=16, height=32, fill=None):
    """Create a 32-bit float raw image file, 16x32, optional header offset. Fill is a list of (x,y,val) triples
    to write."""

    # create black mono image, 16x32 - coords are y,x because we're row-major
    img = np.zeros((height, width), dtype=np.uint16)

    if fill is not None:
        for x, y, v in fill:
            img[y, x] = v

    fn = os.path.join(dir, fn)

    # write it out
    with open(fn, "wb") as f:
        # first write out a header of "offset" bytes, each of which is 10 (just to make it a bit more interesting)
        f.write(b'\x0A' * offset)
        for i in range(height):
            endianness = ">" if bigendian else "<"
            f.write(struct.pack(f"{endianness}{width}f", *img[i]))


def create_raw_uint8(dir, fn, offset=0, bigendian=False, width=16, height=32, fill=None):
    """Create a 8-bit raw image file, 16x32, optional header offset. Fill is a list of (x,y,val) triples
    to write."""

    # create black mono image, 16x32 - coords are y,x because we're row-major
    img = np.zeros((height, width), dtype=np.uint8)

    if fill is not None:
        for x, y, v in fill:
            img[y, x] = v

    fn = os.path.join(dir, fn)

    # write it out
    with open(fn, "wb") as f:
        # first write out a header of "offset" bytes, each of which is 10 (just to make it a bit more interesting)
        f.write(b'\x0A' * offset)
        for i in range(height):
            endianness = ">" if bigendian else "<"
            f.write(struct.pack(f"{endianness}{width}B", *img[i]))


def create_dir_of_raw(fn, dir, offset, bigendian):
    # first image has topleft = 1 and bottomleft = 65535 (these get divided down so that 65535->1)
    fn(dir, "Test-L01.raw", offset=offset, bigendian=bigendian, width=16, height=32,
       fill=[(0, 0, 1), (0, 31, 65535)])
    # second image has topleft = 2 and topright = 2
    fn(dir, "Test-L02.raw", offset=offset, bigendian=bigendian, width=16, height=32,
       fill=[(0, 0, 2), (15, 0, 2)])


def test_endianness_correct():
    """Test that raw test files do in fact have the correct endianness!"""
    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # that should have written the uint16 value 1 to the first pixel. In littleendian that would be 1,0
        with open(os.path.join(d, "Test-L01.raw"), "rb") as f:
            data = f.read()
            assert data[:2] == b'\x01\x00'

        create_dir_of_raw(create_raw_uint16, d, 0, True)
        # that should have written the uint16 value 1 to the first pixel. In bigendian that would be 0,1
        with open(os.path.join(d, "Test-L01.raw"), "rb") as f:
            data = f.read()
            assert data[:2] == b'\x00\x01'


def test_offset_correct():
    """Check that files are created with a correct offset"""
    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 6, True)
        # that should have written the uint16 value 1 to the first pixel, but there will be 6 bytes of 10 first.
        with open(os.path.join(d, "Test-L01.raw"), "rb") as f:
            data = f.read()
            assert data[:6] == b'\x0A\x0A\x0A\x0A\x0A\x0A'
            data = data[6:]
            assert data[:2] == b'\x00\x01'
            data = data[2:]
            assert data[:10] == b"\00" * 10


def test_raw_uint16_bigend():
    """Try to load a raw file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, True)
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, bigendian=True, offset=0, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend():
    """Try to load a raw file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, bigendian=False, offset=0, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    assert img[0, 0][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_offset():
    """Try to load a raw file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 10, False)
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, bigendian=False, offset=10, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    assert img[0, 0][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_rotate():
    """Try rotating on load. We're also testing some defaults here (bigendian false, offset 0 and no flips)"""
    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # now load with a 90 degree CCW rotation
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, rot=90)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    # dimensions should have flipped
    assert img.w == 32
    assert img.h == 16

    assert img[0, 15][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 15][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[31, 15][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[31, 15][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_rotate270():
    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # now load with a 90 degree CCW rotation
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, rot=270)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    # dimensions should have flipped
    assert img.w == 32
    assert img.h == 16

    assert img[31, 0][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[31, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[31, 15][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[31, 15][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_flipv():
    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # now load with a 90 degree CCW rotation
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, vertflip=True)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    # dimensions should have flipped
    assert img.w == 16
    assert img.h == 32

    assert img[0, 31][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 31][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 31][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_fliph():
    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # now load with a 90 degree CCW rotation
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, horzflip=True)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    # dimensions should have flipped
    assert img.w == 16
    assert img.h == 32

    assert img[15, 0][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 31][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[15, 31][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_uint16_littleend_flipboth():
    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_uint16, d, 0, False)
        # now load with a 90 degree CCW rotation
        loader = RawLoader(format=RawLoader.UINT16, width=16, height=32, horzflip=True, vertflip=True)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    # dimensions should have flipped
    assert img.w == 16
    assert img.h == 32

    assert img[15, 31][0].approxeq(Value(1 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 31][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][1].approxeq(Value(2 / 65535, 0, dq.NOUNCERTAINTY))


def test_raw_float32_bigend():
    """Try to load a raw file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_float32, d, 0, True)
        loader = RawLoader(format=RawLoader.FLOAT32, width=16, height=32, bigendian=True, offset=0, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2, 0, dq.NOUNCERTAINTY))


def test_raw_float32_littleend_offset():
    """Try to load a raw file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw(create_raw_float32, d, 32, False)
        loader = RawLoader(format=RawLoader.FLOAT32, width=16, height=32, bigendian=False, offset=32, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(65535, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2, 0, dq.NOUNCERTAINTY))


def create_dir_of_raw2(fn, dir, offset, bigendian):
    # first image has topleft = 1 and bottomleft = 4. Done this because the other create_dir has 65535 and
    # we need to do bytes, and I don't want to modify a lot of code.
    fn(dir, "Test-L01.raw", offset=offset, bigendian=bigendian, width=16, height=32,
       fill=[(0, 0, 1), (0, 31, 255)])
    # second image has topleft = 2 and topright = 2
    fn(dir, "Test-L02.raw", offset=offset, bigendian=bigendian, width=16, height=32,
       fill=[(0, 0, 2), (15, 0, 2)])


def test_raw_byte_offset():
    """Try to load a raw 8-bit file"""

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw2(create_raw_uint8, d, 12, False)
        loader = RawLoader(format=RawLoader.UINT8, width=16, height=32, bigendian=False, offset=12, rot=0,
                           horzflip=False, vertflip=False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1/255, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[0, 31][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[15, 0][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))


def test_raw_byte_offset_rot90_vflip():
    """
    Try to load a raw file. We'll also test rotate and flip together - the order should be rotate first, then flip.
    This is a 90 degree rotate followed by a vertical flip - essentially a transpose.
    """

    pcot.setup()  # filterset can't be found without this

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw2(create_raw_uint8, d, 12, False)
        loader = RawLoader(format=RawLoader.UINT8, width=16, height=32, bigendian=False, offset=12, rot=90,
                           vertflip=True)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"],
                             filterpat=r'.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
                             filterset='AUPE',
                             rawloader=loader
                             )

    img = img.get(Datum.IMG)
    assert img.w == 32
    assert img.h == 16

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1/255, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))
    assert img[31, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[31, 0][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 15][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 15][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))


def test_preset_raw():
    """
    Here we test loading a raw file using a preset. Because presets are user-defined, this is tricky -
    I add a preset to the preset system by hand, rather than having it loaded at startup.
    """

    from pcot.inputs.multifile import presetModel
    pcot.setup()

    # create a preset by hand
    loader = RawLoader(format=RawLoader.UINT8, width=16, height=32, bigendian=False, offset=12, rot=90,
                       vertflip=True)
    # The preset is stored as a dict
    preset = {
        'rawloader': loader.serialise(),
        'filterpat': '.*Test-(?P<lens>L|R)(?P<n>[0-9][0-9]).*',
        'filterset': 'AUPE'
    }
    presetModel.addPreset("testpreset", preset)

    with tempfile.TemporaryDirectory() as d:
        create_dir_of_raw2(create_raw_uint8, d, 12, False)
        img = load.multifile(d, ["Test-L01.raw", "Test-L02.raw"], preset='testpreset')

    img = img.get(Datum.IMG)
    assert img.w == 32
    assert img.h == 16

    # check the wavelengths are correct for AUPE positions 01 and 02.
    assert img.sources[0].getOnlyItem().getFilter().cwl == 440
    assert img.sources[1].getOnlyItem().getFilter().cwl == 540

    assert img[0, 0][0].approxeq(Value(1/255, 0, dq.NOUNCERTAINTY))
    assert img[0, 0][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))
    assert img[31, 0][0].approxeq(Value(1, 0, dq.NOUNCERTAINTY))
    assert img[31, 0][1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 15][0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert img[0, 15][1].approxeq(Value(2/255, 0, dq.NOUNCERTAINTY))

