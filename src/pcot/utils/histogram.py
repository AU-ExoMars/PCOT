"""
Histograms of the bands of an image, as made by the histogram node. Kept free of Qt so that library and
notebook users can make and plot them too.
"""

from __future__ import annotations
from typing import List, Optional, Dict

import numpy as np

from pcot.documentsettings import DocumentSettings
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.sources import SourcesObtainable, SourceSet
from pcot.utils.table import Table
from pcot.utils.tabular_provider import TabularProvider, TabularIterator


def _edges(lo, hi, bincount):
    """Bin edges for a histogram over a range. We work these out ourselves, in float64 narrowed to float32,
    rather than using the ones np.histogram returns: numpy 2 calculates its edges directly in float32, which
    makes them differ in the last digit from numpy 1. These are the same on both (and are what numpy 1
    returned). Like np.histogram, an empty range is widened by 0.5 each way."""
    lo, hi = float(lo), float(hi)
    if lo == hi:
        lo, hi = lo - 0.5, hi + 0.5
    return np.linspace(lo, hi, bincount + 1, dtype=np.float64).astype(np.float32)


class Histogram(SourcesObtainable):
    """Histograms of the bands of an image, all over the same range and so sharing the same bins.

    * labels - a label for each band
    * counts - array of shape (bands, bincount): the number of pixels of each band in each bin
    * edges - the bin edges, bincount+1 of them

    Make one from an image with Histogram.fromImage(). In a Jupyter notebook it displays as a plot;
    plot() draws it onto matplotlib axes, and table() gives the counts as a PCOT Table.
    """
    labels: List[str]
    counts: np.ndarray
    edges: np.ndarray

    def __init__(self, labels, counts, edges, sources: Optional[SourceSet] = None):
        self.labels = list(labels)
        self.counts = np.asarray(counts)
        self.edges = np.asarray(edges)
        if self.counts.shape != (len(self.labels), len(self.edges) - 1):
            raise ValueError(f"counts should have shape {(len(self.labels), len(self.edges) - 1)}, "
                             f"not {self.counts.shape}")
        self.sources = sources if sources is not None else SourceSet()

    def getSources(self):
        return self.sources


    @classmethod
    def fromImage(cls, img, bincount: int = 16, captionType: int = DocumentSettings.CAP_DEFAULT) -> 'Histogram':
        """Histogram each band of an image (an ImageCube, or a Datum holding one). Only pixels in the image's
        regions of interest are counted, if it has any, and BAD pixels in each band are not counted. The bins
        span the range of the counted pixels, across all bands. Uncertainty is ignored. captionType says how bands are labelled (see DocumentSettings)."""
        from pcot.datum import Datum
        if isinstance(img, Datum):
            d = img.get(Datum.IMG)
            if d is None:
                raise TypeError("the Datum doesn't hold an image")
            img = d
        subimg = img.subimage()
        # we get a mask - this has a layer for each channel. Each True value will be considered a weight of 1,
        # each False is a weight of 0. That means that areas outside the ROI and BAD pixels in channels will
        # not be counted.
        weights = subimg.fullmask(True).astype(float)
        data = subimg.img
        if data.ndim == 2:
            data, weights = data[:, :, np.newaxis], weights[:, :, np.newaxis]
        labels = [f"{i}: {s.brief(captionType)}" for i, s in enumerate(img.sources.sourceSets)]
        assert len(labels) == data.shape[2]
        # all bands share a range, so they can be compared. It only covers the pixels which are counted, so
        # BAD pixels and those outside the ROI (but inside its bounding box) can't stretch it. If no pixels
        # are counted at all, the counts are all zero, over 0-1.
        counted = data[weights > 0]
        if counted.size > 0:
            lo, hi = counted.min(), counted.max()
        else:
            lo, hi = 0, 1
        edges = _edges(lo, hi, bincount)
        rng = (float(edges[0]), float(edges[-1]))
        counts = np.array([np.histogram(data[:, :, i], bincount, range=rng, weights=weights[:, :, i])[0]
                           for i in range(data.shape[2])])
        return cls(labels, counts, edges, SourceSet(img.sources))

    @property
    def bincount(self) -> int:
        return len(self.edges) - 1

    def __len__(self):
        """number of bands"""
        return len(self.labels)

    def __repr__(self):
        return f"Histogram({len(self)} bands, {self.bincount} bins, {self.edges[0]:g} to {self.edges[-1]:g})"

    def table(self) -> Table:
        """The counts as a table: a row for each band, a column for each bin labelled with its lower edge"""
        t = Table()
        for lab, counts in zip(self.labels, self.counts):
            t.newRow(lab)
            t.add('band', lab)
            for k, v in zip(self.edges, counts):
                t.add(k, v)
        return t

    def plot(self, ax=None):
        """Plot the histograms onto matplotlib axes, or a new figure if none are given; returns the axes"""
        import pcot.plotting
        return pcot.plotting.histogram(self, ax)

    def _repr_png_(self):
        """Jupyter display: the histograms as a plot"""
        import pcot.plotting
        return pcot.plotting.histogramPNG(self)

    # table provider gubbins

    class Provider(TabularProvider):
        def __init__(self, h: Histogram):
            self.h = h

        def getParams(self) -> Optional[TaggedDict]:
            return None

        def getHeaders(self) -> List[str]:
            """bins are rows"""
            return ["bin"] + self.h.labels

        def __iter__(self) -> TabularIterator:
            return Histogram.Provider.RowIterator(self)

        class RowIterator(TabularIterator):
            def __init__(self, provider: Histogram.Provider):
                self.h = provider.h
                self.headers = provider.getHeaders()
                # we're going to iterate over the indices,
                # so we can index into the edge and count arrays
                # with the index.
                self.iter = iter(range(len(self.h.edges)))

            def __next__(self) -> Dict[str, str]:
                idx = next(self.iter) # throws StopIteration to halt
                edge = self.h.edges[idx]
                count_array = self.h.counts[idx]

                # the label for this bin
                binlabel = str(edge)    # TODO fix format

                # count for each label in this bin
                data = [count_array[x] for x in range(0,len(self.h.labels))]
                data = [str(x) for x in data] # TODO fix format

                out =  {
                    "bin": binlabel,
                }
                # TODO rewrite this better
                for idx,label in enumerate(self.h.labels):
                    out[label] = data[idx]

                return out
