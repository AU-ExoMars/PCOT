import numpy

from pcot.datum import Datum

from fixtures import *
from pcot.document import Document


def test_datum_can_create_and_serialise_img(bwimage):
    doc = Document()
    img = Datum(Datum.IMG, bwimage)
    tp, datadict = img.serialise()

    # make some assumptions about what's in the data dict!
    assert tp == 'img'
    assert datadict['mapping'] == [2, 1, 0]
    assert datadict['defmapping'] is None
    assert datadict['sources'] == [[], [], []]
    assert type(datadict['data']) == numpy.ndarray
    arr = datadict['data']
    assert arr.shape == (32, 32, 3)

    # deserialise - note that we deserialise the data dictionary,
    # not the tuple that comes out of serialise.
    img = ImageCube.deserialise(datadict, doc)
    assert img.channels == 3
    assert img.h == 32
    assert img.w == 32

    assert np.array_equal(img.img[0][0], [1, 1, 1])
    assert np.array_equal(img.img[img.h - 1][img.w - 1], [0, 0, 0])

