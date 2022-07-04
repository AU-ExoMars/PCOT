from pcot.datum import Datum

from fixtures import *

def test_datum_can_create_and_serialise_img(bwimage):
    img = Datum(Datum.IMG, bwimage)
    xx = img.serialise()
