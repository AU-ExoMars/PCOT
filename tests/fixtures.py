from gen_envi import gen_envi
from pcot.imagecube import ImageCube, ChannelMapping

import os
import pathlib

import pytest
from distutils import dir_util
import numpy as np

from pcot.sources import MultiBandSource, nullSource

"""
Assorted test fixtures, mainly for generating input data (typically images)
"""


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
    raise FileNotFoundError(f"cannot find tests/data in parents of test directory {path}")


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


@pytest.fixture
def allblack():
    """Generate an all black 16x8 RGB image"""
    sources = MultiBandSource([nullSource, nullSource, nullSource])
    bands = np.dstack([np.full((8, 16), 0.0) for i in range(3)]).astype(np.float32)
    assert bands.shape == (8, 16, 3)
    imgc = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None)
    assert imgc.w == 16
    assert imgc.h == 8
    return imgc


def fillrect(img, x, y, w, h, v):
    img[y:y + h, x:x + w] = v


@pytest.fixture
def envi_image_1(tmp_path):
    fn = tmp_path / "temp"
    freqs = (800, 640, 550, 440)

    # this is h,w order - so an 80x60 image
    img = np.zeros((60, 80, len(freqs)), dtype=np.float32)
    # fill the rectangle x=50, y=40, w=20, h=10
    # with (1,0,1,1)
    fillrect(img, 50, 40, 20, 10, (1, 0, 1, 1))

    # write the data
    gen_envi(fn, freqs, img)

    # return the filename (with a .hdr)
    return fn.with_suffix(".hdr")
