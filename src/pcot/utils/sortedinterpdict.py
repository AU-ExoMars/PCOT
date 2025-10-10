"""
I need to store data in a dict but...
1) the data needs to maintain an ordering of keys, which are numeric
2) I need to be able to retrieve the two key/value pairs "around" a given key value
3) I need to be able to optionally handle "cyclic" data, such as when the keys are angles around a circle.
"""


class SortedInterpolatedDict:
    def __init__(self, keys=None, values=None, period=None):
        """Create a sorted interpolated dict.
        If keys and values are given, they must be the same length.
        If period is given, the dict is treated as cyclic, with the given period. The period must run from 0 to this value.
        We assume that keys are numeric (int or float) and that the dict is immutable.
        """
        self.period = period
        self.keys = []
        self.dict = {}
        if values is None:
            raise ValueError("If keys are given, values must also be given")
        if len(keys) != len(values):
            raise ValueError("Keys and values must be the same length")
        for k, v in zip(keys, values):
            self.dict[k] = v
        self.keys = sorted(keys)

    def serialise(self):
        """Return a JSON-serialisable representation"""
        return {"keys":self.keys, "values": [self.dict[x] for x in self.keys], "period":self.period}

    @staticmethod
    def deserialise(d):
        """Take a JSON-serialisable rep, and convert back to object.
        Assumes the stored data is JSON-serialisable, which it may
        not be.
        JSON has string keys - "convert" controls how these are treated; either using int or
        float conversion.
        """
        keys = d["keys"]
        values = d["values"]
        obj = SortedInterpolatedDict(d["keys"],d["values"],d["period"])
        return obj


    def __getitem__(self, key):
        return self.dict[key]

    def __contains__(self, item):
        return item in self.dict

    def __rdivmod__(self, other):
        """So we can do other % self to get the equivalent key in the dict if it's cyclic"""
        return divmod(other, self.period) if self.period is not None else (None, other)

    def around(self, k):
        """return the two keys around the given key k. If the dict is cyclic, this will wrap around.
        If k is exactly a key in the dict, return (k, k). If the dict is empty, raise ValueError.
        If k is outside the range of keys and the dict is not cyclic, return the nearest end key twice.
        """
        if len(self.dict) == 0:
            raise ValueError("Dict is empty")
        if k in self.keys:
            return k, k
        if self.period is not None:
            # cyclic case
            while k<0:
                k += self.period
            k = k % self.period
            if k in self.dict:
                return k, k
            if k < self.keys[0]:
                return self.keys[-1], self.keys[0]
            if k > self.keys[-1]:
                return self.keys[-1], self.keys[0]
        else:
            # non-cyclic case - just clamp to the ends
            if k < self.keys[0]:
                return self.keys[0], self.keys[0]
            if k > self.keys[-1]:
                return self.keys[-1], self.keys[-1]
        # now find the two keys between which k lies
        for i in range(len(self.keys) - 1):
            if self.keys[i] < k < self.keys[i + 1]:
                return self.keys[i], self.keys[i + 1]

        raise ValueError("Key not found")


def test_basic():
    d = SortedInterpolatedDict(keys=[10, 20, 30], values=['a', 'b', 'c'])
    assert d[10] == 'a'
    assert d[20] == 'b'
    assert d[30] == 'c'
    assert d.around(10) == (10, 10)
    assert d.around(20) == (20, 20)
    assert d.around(30) == (30, 30)
    assert d.around(15) == (10, 20)
    assert d.around(25) == (20, 30)
    assert d.around(5) == (10, 10)
    assert d.around(35) == (30, 30)


def test_cyclic():
    d = SortedInterpolatedDict(keys=[0, 90, 180, 270], values=['a', 'b', 'c', 'd'], period=360)
    assert d[0] == 'a'
    assert d[90] == 'b'
    assert d[180] == 'c'
    assert d[270] == 'd'
    assert d.around(0) == (0, 0)
    assert d.around(90) == (90, 90)
    assert d.around(180) == (180, 180)
    assert d.around(270) == (270, 270)
    assert d.around(360) == (0, 0)

    assert d.around(45) == (0, 90)
    assert d.around(135) == (90, 180)
    assert d.around(225) == (180, 270)
    assert d.around(315) == (270, 0)
    assert d.around(-45) == (270, 0)
    assert d.around(450) == (90, 90)
    assert d.around(720) == (0, 0)
    assert d.around(-10) == (270, 0)
    assert d.around(-370) == (270, 0)
    assert d.around(365) == (0, 90)
