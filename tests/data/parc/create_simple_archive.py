import pcot
from pcot.utils.archive import FileArchive
import numpy as np

test_data_d1 = {
    "foo": 1,
    "bar": "hello",
    "baz": np.array([1, 2, 3])
}

test_data_d2 = {
    "foo": 2,
    "bar": "world",
    "baz": np.array([4, 5, 6]),
    "lst": [1, 2, 3],
    "d": {
        "a": 1,
        "b": 2,
        "c": [1, 2, 3],
        "d": np.array([10, 20, 30, 40]).reshape(2, 2)
    }
}

pcot.setup()


with FileArchive("testarch.dat","w") as a:
    a.writeJson("data1", test_data_d1)
    a.writeJson("data2", test_data_d2)
    

