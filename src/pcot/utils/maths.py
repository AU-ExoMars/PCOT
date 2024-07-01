import numpy as np


def pooled_sd(n, u):
    """Returns pooled standard deviation for an array of nominal values and an array of stddevs."""
    # "Thus the variance of the pooled set is the mean of the variances plus the variance of the means."
    # by https://arxiv.org/ftp/arxiv/papers/1007/1007.1012.pdf
    # the variance of the means is n.var()
    # the mean of the variances is np.mean(u**2) (since u is stddev, and stddev**2 is variance)
    # so the sum of those is pooled variance. Root that to get the pooled stddev.
    varianceOfMeans = n.var()           # variance of the means
    meanOfVariances = np.mean(u ** 2)   # get all the SDs, square them to convert to variances, then get the mean of those.
    return np.sqrt(varianceOfMeans + meanOfVariances)
