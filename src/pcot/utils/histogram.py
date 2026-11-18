"""
Histograms of the bands of an image, as made by the histogram node. Kept free of Qt so that library and
notebook users can make and plot them too.
"""

from __future__ import annotations
from collections import Counter
from typing import List, Optional, Dict

import numpy as np

import pcot.config

from pcot.documentsettings import DocumentSettings
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.sources import SourcesObtainable, SourceSet
from pcot.utils.table import printable
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


# column headers in the table for the bin edges; band labels must not be these
BIN_HEADERS = ["lower", "upper"]


def _bandLabels(img) -> List[str]:
    """Labels for the bands of an image, which must be unique (they are table column headers). A band with
    a single filter is labelled with its wavelength, as in spectrum tables. Bands without one (e.g. derived
    from several bands), or sharing a wavelength with another band, are labelled with their sources. If
    labels still clash, the band index is added."""
    labels = []
    for i in range(img.channels):
        w = img.wavelength(i)
        labels.append(f"{w:g}" if w >= 0 else None)
    counts = Counter(x for x in labels if x is not None)
    for i, lab in enumerate(labels):
        if lab is None or counts[lab] > 1:
            labels[i] = img.sources.sourceSets[i].brief(DocumentSettings.CAP_CWL) or f"band {i}"
    counts = Counter(labels)
    return [f"{lab} #{i}" if counts[lab] > 1 or lab in BIN_HEADERS else lab for i, lab in enumerate(labels)]


def _edgeLabels(edges) -> List[str]:
    """Bin edges as strings, to the configured number of significant figures - or more, if needed to make
    them all different (with very narrow bins). 9 figures always distinguishes different float32 values."""
    sf = pcot.config.data.sigfigs
    while True:
        labels = [printable(e, sf) for e in edges]
        if len(set(labels)) == len(labels) or sf >= 9:
            return labels
        sf += 1


class Histogram(SourcesObtainable):
    """Histograms of the bands of an image, all over the same range and so sharing the same bins.

    * labels - a label for each band
    * counts - array of shape (bands, bincount): the number of pixels of each band in each bin
    * edges - the bin edges, bincount+1 of them

    Make one from an image with Histogram.fromImage(). In a Jupyter notebook it displays as a plot;
    plot() draws it onto matplotlib axes, and tabularProvider() gives it as a table with a row for each bin
    and a column for each band.
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
        # labels are table column headers, so must be unique and not clash with the bin edge headers
        if len(set(self.labels)) != len(self.labels) or set(self.labels) & set(BIN_HEADERS):
            raise ValueError(f"band labels must be unique and not {' or '.join(BIN_HEADERS)}: {self.labels}")
        self.sources = sources if sources is not None else SourceSet()

    def getSources(self):
        return self.sources

    def serialise(self):
        """Serialise; the sources are not included, and are serialised separately by the Datum type"""
        return {
            "labels": self.labels,
            "counts": self.counts.tolist(),
            "edges": self.edges.tolist(),
        }

    @staticmethod
    def deserialise(data, sources: Optional[SourceSet] = None) -> Histogram:
        return Histogram(data["labels"], np.array(data["counts"]),
                         np.array(data["edges"], dtype=np.float32), sources)

    @classmethod
    def fromImage(cls, img, bincount: int = 16) -> 'Histogram':
        """Histogram each band of an image (an ImageCube, or a Datum holding one). Only pixels in the image's
        regions of interest are counted, if it has any, and BAD pixels in each band are not counted. The bins
        span the range of the counted pixels, across all bands. Uncertainty is ignored. Bands are labelled
        with their wavelengths where they have a single filter, or with their sources otherwise."""
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
        labels = _bandLabels(img)
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
            """bins are rows: the bin's lower and upper edges, then the count for each band"""
            return BIN_HEADERS + self.h.labels

        def __iter__(self) -> TabularIterator:
            return Histogram.Provider.RowIterator(self)

        class RowIterator(TabularIterator):
            def __init__(self, provider: Histogram.Provider):
                self.h = provider.h
                # edges are formatted here rather than when the histogram is made, so they follow the
                # current sigfigs setting
                self.edgeLabels = _edgeLabels(self.h.edges)
                # there is one fewer bin than edges
                self.iter = iter(range(self.h.bincount))

            def __next__(self) -> Dict[str, str]:
                idx = next(self.iter)  # throws StopIteration to halt
                out = {"lower": self.edgeLabels[idx], "upper": self.edgeLabels[idx + 1]}
                # counts array is indexed as (band,bin); counts are whole numbers
                for band, label in enumerate(self.h.labels):
                    out[label] = str(int(self.h.counts[band, idx]))
                return out

    def tabularProvider(self):
        """Return a tabular provider: a row for each bin, a column for each band"""
        return Histogram.Provider(self)

    def __str__(self):
        return self.tabularProvider().csvString()
