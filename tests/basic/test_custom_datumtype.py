"""
Very simple test of a custom datum type, showing that it can store numpy array data in
a DatumStore archive. Also shows how to use one of those.
"""
import tempfile

import numpy as np

from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.sources import nullSourceSet
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore


class TestDatumType(Type):
    def __init__(self):
        super().__init__("testdatumtype", internal = True, valid ={np.ndarray})

    def copy(self,d):
        return d

    def serialise(self,d:Datum):
        # return (name, value) - array serialisation is handled automatically so we don't
        # need to do anything there.
        return self.name, d.val

    def deserialise(self,d):
        return Datum(self, d, nullSourceSet)

Datum.registerType(TEST_DATUM_TYPE:=TestDatumType())

def test_store_datum_with_nparray():
    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.parc"
        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            da = DatumStore(a)
            # create some data
            arr = np.array([10,20,30,40], dtype=np.float32)
            td = Datum(TEST_DATUM_TYPE, arr, nullSourceSet)
            da.writeDatum("test", td)

        # read it back
        a = DatumStore(FileArchive(fn), 1000)
        d = a.get("test")
        assert np.array_equal(d.val, arr)

