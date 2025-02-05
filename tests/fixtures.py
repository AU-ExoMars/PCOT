from tests.gen_envi import gen_envi
from pcot import dq
from pcot.imagecube import ImageCube, ChannelMapping

import os
import pathlib

import pytest
from distutils import dir_util
import numpy as np

from pcot.sources import MultiBandSource, nullSource, Source

"""
Assorted test fixtures, mainly for generating input data (typically images)
"""


def checkexpr(expr):
    """Check an expression node for errors"""
    if expr.error is not None:
        pytest.fail(f"Error in expression: {expr.error}")


@pytest.fixture
def datadir(tmp_path, request):
    """
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely. Returns a pathlib.

    To use this, the data files need to be in a directory with the same name as the test module,
    with "_data" added:
    e.g. "test_foo.py" needs a directory called "test_foo_data" in the same place.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    test_dir += "_data"
    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmp_path))
    else:
        raise Exception(f"Test data directory {test_dir} does not exist")

    return tmp_path


@pytest.fixture
def globaldatadir(tmp_path, request):
    """
    As datadir, but this uses the "PCOT/tests/data" directory rather than a per-module directory.
    """
    path = pathlib.Path(request.module.__file__).resolve()
    # walk the module's path until we find an element called "tests" which has a child called "data"
    parents = path.parents
    for i in range(len(parents) - 1):
        if parents[i].name == 'tests' and (parents[i] / 'data').exists():
            xx = parents[i] / 'data'
            return xx
    raise Exception(f"cannot find tests/data in parents of test directory {path}")


@pytest.fixture
def bwimage(globaldatadir):
    """Fixture to load a b/w image"""
    path = globaldatadir / 'basn0g01.png'
    return ImageCube.load(str(path), None, None)


@pytest.fixture
def rectimage(globaldatadir):
    """Fixture to load a rectangular test image"""
    path = globaldatadir / 'rect1.png'
    return ImageCube.load(str(path), None, None)


def genmono(w,h,v,u,dq,inpidx=None):
    if inpidx is not None:
        s = Source().setBand('M')
        sources = MultiBandSource([s])
    else:
        sources = MultiBandSource([nullSource])

    band = np.full((h,w),v).astype(np.float32)
    u = np.full((h,w),u).astype(np.float32)
    dq = np.full((h,w),dq).astype(np.uint16)

    imgc = ImageCube(band, ChannelMapping(), sources, defaultMapping=None, uncertainty=u, dq=dq)
    assert imgc.w == w
    assert imgc.h == h
    return imgc


def genrgb(w, h, r, g, b, u=None, d=None, inpidx=None):
    """Generate an RGB image.
    If u is provided, it is an (r,g,b) uncertainty tuple.
    If d is provided, it is an (r,g,b) dq bits tuple

    """
    # These are generated as "orphan" sources that come from no real input unless
    # an index is specified (it's OK to call setInputIdx with None).
    sources = MultiBandSource([Source().setBand('R').setInputIdx(inpidx),
                               Source().setBand('G').setInputIdx(inpidx),
                               Source().setBand('B').setInputIdx(inpidx)])

    bands = [np.full((h, w), x) for x in (r, g, b)]
    bands = np.dstack(bands).astype(np.float32)
    assert bands.shape == (h, w, 3)

    if u is not None:
        u = [np.full((h, w), x) for x in u]
        u = np.dstack(u).astype(np.float32)
    else:
        u = None

    if d is not None:
        d = [np.full((h, w), x) for x in d]
        d = np.dstack(d).astype(np.uint16)
    else:
        d = None

    imgc = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None, uncertainty=u, dq=d)
    assert imgc.w == w
    assert imgc.h == h
    return imgc


def gen_two_halves(w, h, v1, u1, v2, u2,     inpidx=None):
    """Generate an image of two halves. The top half is value v1 and uncertainty u1, the bottom half is v2,u2.
    Each of the values must be a tuple.
    """

    if inpidx is not None:
        # generate source names of the form r,g,b,c3,c4..
        sourceNames = ["r", "g", "b"] + [f"c{i}" for i in range(3, len(v1))]
        sources = MultiBandSource([Source().setBand(sourceNames[i]) for i in range(0, len(v1))])
    else:
        sources = MultiBandSource([nullSource] * len(v1))

    h2 = int(h/2)
    bands1 = np.dstack([np.full((h2, w), x) for x in v1]).astype(np.float32)
    bands2 = np.dstack([np.full((h2, w), x) for x in v2]).astype(np.float32)
    bands = np.vstack((bands1, bands2))
    unc1 = np.dstack([np.full((h2, w), x) for x in u1]).astype(np.float32)
    unc2 = np.dstack([np.full((h2, w), x) for x in u2]).astype(np.float32)
    uncs = np.vstack([unc1, unc2])

    assert bands.shape == (h, w, len(v1))
    imgc = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None, uncertainty=uncs)
    assert imgc.w == w
    assert imgc.h == h
    return imgc


@pytest.fixture
def allblack():
    """Generate an all black 16x8 RGB image"""
    return genrgb(16, 8, 0, 0, 0)


def fillrect(img, x, y, w, h, v):
    img[y:y + h, x:x + w] = v


@pytest.fixture
def envi_image_1(tmp_path):
    """generate a 4-channel 80x60 image, zeroed but with a rectangle filled in"""
    freqs = (800, 640, 550, 440)
    fn = tmp_path / "temp_envi_1"

    # this is h,w order - so an 80x60 image
    img = np.zeros((60, 80, len(freqs)), dtype=np.float32)
    # fill the rectangle x=50, y=40, w=20, h=10
    # with (1,0,1,1)
    fillrect(img, 50, 40, 20, 10, (1, 0, 1, 1))

    # write the data
    gen_envi(fn, freqs, img)

    # return the filename (with a .hdr)
    return fn.with_suffix(".hdr")


@pytest.fixture
def envi_image_2(tmp_path):
    """generate a 4-channel 80x60 image, zeroed but with a rectangle filled in"""
    freqs = (1000, 2000, 3000, 4000)
    fn = tmp_path / "temp_envi_2"

    # this is h,w order - so an 80x60 image
    img = np.zeros((60, 80, len(freqs)), dtype=np.float32)
    # fill the rectangle x=10, y=10, w=20, h=20
    # with (0,1,1,0.5)
    fillrect(img, 10, 10, 20, 20, (0, 1, 1, 0.5))

    # write the data
    gen_envi(fn, freqs, img)

    # return the filename (with a .hdr)
    return fn.with_suffix(".hdr")

