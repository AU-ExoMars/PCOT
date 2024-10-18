"""Tests on basic datum operations such as serialization"""

import numpy

import pcot
from pcot.datum import Datum
from pcot.sources import SourceSet
from pcot.value import Value

from fixtures import *
from pcot.document import Document


def test_datum_can_create_and_serialise_img(bwimage):
    """This ensures that a Datum can serialise and deserialise an image
    with uncertainty and DQ as well as nominal pixel data. This relies
    on Value working."""
    pcot.setup()
    
    doc = Document()

    data = genrgb(32,32,
                  1.1, 2.2, 3.3,    # rgb
                  u=(0.1, 0.2, 0.3), # unc
                  d=(dq.NONE, dq.UNDEF, dq.DIVZERO) # dq
                  )

    img = Datum(Datum.IMG, data)
    tp, datadict = img.serialise()

    # make some assumptions about what's in the data dict!
    assert tp == 'img'
    # this is arbitrary - 0,1,2 is the RGB channel order when you don't know anything better.
    # It used to be 2,1,0 but that caused problems in inset.
    assert datadict['mapping'] == [0, 1, 2]
    assert datadict['defmapping'] is None
    expected_sources = [
        [{'external': None, 'band': 'R', 'inputIdx': None}],
        [{'external': None, 'band': 'G', 'inputIdx': None}],
        [{'external': None, 'band': 'B', 'inputIdx': None}]
    ]
    assert datadict['sources'] == expected_sources
    assert type(datadict['data']) == numpy.ndarray
    arr = datadict['data']
    assert arr.shape == (32, 32, 3)

    # deserialise - note that we deserialise the data dictionary,
    # not the tuple that comes out of serialise.
    img = ImageCube.deserialise(datadict, doc)
    assert img.channels == 3
    assert img.h == 32
    assert img.w == 32

    r, g, b = img[0,0]
    assert r.approxeq(Value(1.1, 0.1, dq.NONE))
    assert not r.approxeq(Value(1.6, 0.1, dq.NONE))
    assert g.approxeq(Value(2.2, 0.2, dq.UNDEF))
    assert b.approxeq(Value(3.3, 0.3, dq.DIVZERO))

    # and we'll check at the low level too, for the actual pixel values
    assert not np.allclose(img.img[0][0], (5.1, 2.2, 3.3))
    assert np.allclose(img.img[0][0], (1.1, 2.2, 3.3))
    assert np.allclose(img.img[img.h - 1][img.w - 1], (1.1,2.2,3.3))
    assert np.allclose(img.uncertainty[0][0], (0.1, 0.2, 0.3))
    assert np.allclose(img.uncertainty[img.h - 1][img.w - 1], (0.1,0.2,0.3))
    assert np.allclose(img.dq[0][0], (dq.NONE, dq.UNDEF, dq.DIVZERO))
    assert np.allclose(img.dq[img.h-1][img.w-1], (dq.NONE, dq.UNDEF, dq.DIVZERO))



