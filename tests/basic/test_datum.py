"""Tests on basic datum operations such as serialization"""

import numpy

import pcot
from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.rois import ROIRect
from pcot.sources import SourceSet, nullSourceSet
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
        [{'external': None, 'band': 'R', 'inputIdx': None, 'secondary_name': None}],
        [{'external': None, 'band': 'G', 'inputIdx': None, 'secondary_name': None}],
        [{'external': None, 'band': 'B', 'inputIdx': None, 'secondary_name': None}]
    ]
    assert datadict['sources'] == expected_sources
    assert type(datadict['data']) == numpy.ndarray
    arr = datadict['data']
    assert arr.shape == (32, 32, 3)

    # deserialise - note that we deserialise the data dictionary,
    # not the tuple that comes out of serialise.
    img = ImageCube.deserialise(datadict)
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


def test_datum_str_all_types():
    """Datum.__str__ should produce a "<value> (<type name>)" string for every builtin Datum type
    without raising. Build a representative value for each type exposed as a Datum.<CONST>, rather
    than hardcoding the list by hand, so a new builtin type added later fails this test until it's
    covered here. (We use the Datum.<CONST> attributes rather than the global typesByName registry,
    since other test modules register their own ad-hoc types into that registry as a side effect of
    being imported, which would make this test's coverage depend on test run order.)"""
    pcot.setup()

    roi = ROIRect()
    roi.set(0, 0, 4, 4)

    img = genrgb(4, 4, 1.0, 2.0, 3.0)

    values_by_type_name = {
        'any': None,
        'img': img,
        'roi': roi,
        'number': Value(3.0, 0.5, dq.NONE),
        'variant': None,
        'table': None,
        'data': None,
        'testresult': [],
        'ident': 'someident',
        'string': 'somestring',
        'func': None,
        'none': None,
        'cameradata': None,
    }

    builtin_types = {v.name: v for v in vars(Datum).values() if isinstance(v, Type)}

    # if this fails, a builtin Datum type has been added or removed and values_by_type_name needs updating
    assert set(values_by_type_name.keys()) == set(builtin_types.keys())

    for name, val in values_by_type_name.items():
        d = Datum(builtin_types[name], val, sources=nullSourceSet)
        assert str(d) == f"{val} ({name})"

