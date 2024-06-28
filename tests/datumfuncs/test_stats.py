import numpy as np

import pcot
import pcot.dq
from pcot.datum import Datum
import pcot.datumfuncs as df

def test_flatmean():
    seq = [x for x in range(100)]
    x = [Datum.k(x) for x in seq]
    r = df.mean(*x)
    assert r.get(Datum.NUMBER).n == np.mean(seq).astype(np.float32)
    assert r.get(Datum.NUMBER).u == np.std(seq).astype(np.float32)

    # let's see if it works with an image

    imgd = df.testimg(0)
    data = imgd.get(Datum.IMG).img.flatten()
    r = df.mean(imgd)
    assert r.get(Datum.NUMBER).n == np.mean(data).astype(np.float32)
    assert r.get(Datum.NUMBER).u == np.std(data).astype(np.float32)

    # and let's check the pooling. It's best to do this with something with
    # rather less variation in it.

    x = [Datum.k(10+x/100, x/1000) for x in range(100)]
    seq = [10+x/100 for x in range(100)]

    r = df.flatmean(*x)
    assert r.get(Datum.NUMBER).n == np.mean(seq).astype(np.float32)
    # pooled variance is the mean of the variances of the individual samples
    # plus the variance of the means of the individual samples.

    meanOfVariances = np.mean([x.get(Datum.NUMBER).u**2 for x in x])
    varianceOfMeans = np.var([x.get(Datum.NUMBER).n for x in x])
    testu = np.sqrt(meanOfVariances + varianceOfMeans).astype(np.float32)

    assert r.get(Datum.NUMBER).u == testu


def test_sum():
    x = [Datum.k(10+x/100, x/1000) for x in range(100)]
    seq = [10+x/100 for x in range(100)]
    r = df.sum(*x)
    assert r.get(Datum.NUMBER).n == np.sum(seq).astype(np.float32)

    # we're adding standard deviations, so they add in quadrature
    testu = np.sqrt(np.sum([x.get(Datum.NUMBER).u**2 for x in x])).astype(np.float32)
    assert r.get(Datum.NUMBER).u == testu
