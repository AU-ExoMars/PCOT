import numpy as np


def pooled_sd(n, u, axis=None):
    """Returns pooled standard deviation for an array of nominal values and an array of stddevs.
    Will normally operate on the flattened array, but can be restricted to a single axis.
    """
    # "Thus the variance of the pooled set is the mean of the variances plus the variance of the means."
    # by https://arxiv.org/ftp/arxiv/papers/1007/1007.1012.pdf

    # It's a little more complicated than that, because we have to use the number of samples to weight the
    # quantities involved. However, we will make the assumption that the numbers of samples in the underlying
    # sets are all the same. Thus, we can use the unweighted formulae.

    variance_of_means = n.var(axis=None)           # variance of the means

    # get all the SDs, square them to convert to variances, then get the mean of those.
    mean_of_variances = np.mean(u ** 2, axis=None)
    # sum the two, and convert to SD
    return np.sqrt(variance_of_means + mean_of_variances)
