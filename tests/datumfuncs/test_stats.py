import numpy as np

import pcot
import pcot.dq
from fixtures import genrgb
from pcot.datum import Datum
import pcot.datumfuncs as df


def test_mean():
    seq = [x for x in range(100)]
    x = Datum.k(seq)  # this is a sequence of numbers
    r = df.mean(x)
    assert r.get(Datum.NUMBER).n == np.mean(seq).astype(np.float32)
    assert r.get(Datum.NUMBER).u == np.std(seq).astype(np.float32)


def test_mean_image():
    imgd = Datum(Datum.IMG, genrgb(16, 16, 1, 2, 3, (0.1, 0.2, 0.3)))
    r = df.mean(imgd)
    vv = r.get(Datum.NUMBER).n
    assert np.allclose(r.get(Datum.NUMBER).n, np.array([1, 2, 3], dtype=np.float32))
    assert np.allclose(r.get(Datum.NUMBER).u, np.array([0.1, 0.2, 0.3], dtype=np.float32))

    # and let's check the pooling. It's best to do this with something with
    # rather less variation in it.
    ns = [10+x/100 for x in range(100)]
    us = [x/1000 for x in range(100)]
    x = Datum.k(ns, us)     # build a vector Datum with uncertainty

    r = df.mean(x)
    assert r.get(Datum.NUMBER).n == np.mean(ns).astype(np.float32)

    # pooled variance is the mean of the variances of the individual samples
    # plus the variance of the means of the individual samples, but only works
    # if the number of samples in each subset is the same.

    meanOfVariances = np.mean([x ** 2 for x in us])
    varianceOfMeans = np.var(ns)
    testu = np.sqrt(meanOfVariances + varianceOfMeans).astype(np.float32)
    assert np.allclose(r.get(Datum.NUMBER).u, testu)

    # again with flatmean, or rather mean of flat. We flatten the data, then take the mean.

    x = [Datum.k(10 + x / 100, x / 1000) for x in range(100)]
    seq = [10 + x / 100 for x in range(100)]

    r = df.mean(df.flat(*x))
    assert r.get(Datum.NUMBER).n == np.mean(seq).astype(np.float32)
    # pooled variance is the mean of the variances of the individual samples
    # plus the variance of the means of the individual samples, but only works
    # if the number of samples in each subset is the same.

    meanOfVariances = np.mean([x.get(Datum.NUMBER).u ** 2 for x in x])
    varianceOfMeans = np.var([x.get(Datum.NUMBER).n for x in x])
    testu = np.sqrt(meanOfVariances + varianceOfMeans).astype(np.float32)
    assert r.get(Datum.NUMBER).u == testu


def test_sum():
    ns = [10+x/100 for x in range(100)]
    us = [x/1000 for x in range(100)]
    x = Datum.k(ns, us)
    r = df.sum(x)
    assert r.get(Datum.NUMBER).n == np.sum(ns).astype(np.float32)

    # we're adding standard deviations, so they add in quadrature, and they need to be added
    # to the variation in the entire set.
    testu = np.sqrt(np.sum([x ** 2 for x in us]) + np.var(ns)).astype(np.float32)
    assert r.get(Datum.NUMBER).u == testu
