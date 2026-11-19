"""
Plots of PCOT data for use outside the PCOT application - in scripts and Jupyter notebooks. These draw
the same plots as the corresponding nodes, onto ordinary matplotlib axes.

Call pcot.setup() before using these.
"""

import io
from typing import List, Optional

from pcot.plotting.spectrumplot import plotSpectrum, orderLegends

# spectrum node settings which don't affect the plot, and so aren't accepted as plot options
_NON_PLOT_SPECTRUM_SETTINGS = ("sortlist", "ignorePixSD")


def spectrumSettings(**settings):
    """Return the spectrum node's plot settings (a TaggedDict) with their default values, changed by
    any settings given as keyword arguments. Raises TypeError for an unknown setting, and ValueError
    for a value of the wrong type or not in the setting's list of choices."""
    import pcot.xform
    tp = pcot.xform.allTypes.get("spectrum")
    if tp is None:
        raise RuntimeError("PCOT has not been set up - call pcot.setup() first")
    params = tp.params.create()
    valid = [k for k in params.keys() if k not in _NON_PLOT_SPECTRUM_SETTINGS]
    for k, v in settings.items():
        if k not in valid:
            raise TypeError(f"'{k}' is not a spectrum plot setting: valid settings are {', '.join(valid)}")
        params[k] = v
    return params


def _spectrumSet(spectra):
    """Accept a SpectrumSet, or a Datum holding one"""
    from pcot.datum import Datum
    from pcot.utils.spectrumdata import SpectrumSet
    if isinstance(spectra, Datum):
        spectra = spectra.get(Datum.SPECTRA)
        if spectra is None:
            raise TypeError("the Datum doesn't hold a set of spectra")
    if not isinstance(spectra, SpectrumSet):
        raise TypeError(f"expected a SpectrumSet or a Datum holding one, not {type(spectra).__name__}")
    return spectra


def _newAxes(ax):
    """Return the axes given, or new axes in a new pyplot figure (which notebooks show automatically)"""
    if ax is None:
        import matplotlib.pyplot as plt
        _, ax = plt.subplots(layout="constrained")
    return ax


def spectrum(spectra, ax=None, order: Optional[List[str]] = None, **settings):
    """Plot a set of spectra as the spectrum node does, and return the matplotlib Axes.

    * spectra - a SpectrumSet, or a Datum holding one (such as a spectrum node's output)
    * ax - matplotlib Axes to draw on; if None, a new figure is created
    * order - the spectrum names (legends) in the order to plot and stack them; others follow
    * settings - any of the spectrum node's plot settings, for example errorbarmode="stderror",
      stackSep=5, colourmode="scheme2", annotate="line", wavelength_units="microns". See
      spectrumSettings() for the full list and their defaults.
    """
    spectra = _spectrumSet(spectra)
    params = spectrumSettings(**settings)
    ax = _newAxes(ax)
    plotSpectrum(ax, spectra, params, orderLegends(order or [], spectra.keys()))
    return ax


def spectrumFromNode(node, ax=None):
    """Plot a spectrum node's output exactly as the node's own plot shows it - with the node's settings
    and order - and return the matplotlib Axes. The document must have been run."""
    if node.type.name != "spectrum":
        raise TypeError(f"'{node.displayName}' is a {node.type.name} node, not a spectrum node")
    if node.data is None:
        raise ValueError(f"spectrum node '{node.displayName}' has no data - has the document been run?")
    ax = _newAxes(ax)
    plotSpectrum(ax, node.data, node.params, orderLegends(node.params.sortlist.get(), node.data.keys()))
    return ax


def spectrumPNG(spectra, width=8, height=4.5, dpi=100, **settings) -> bytes:
    """Plot a set of spectra with default (or given) settings and return the plot as PNG data. Uses
    matplotlib's Agg renderer directly, so it doesn't create a pyplot figure."""
    spectra = _spectrumSet(spectra)
    fig = _aggFigure(width, height, dpi)
    plotSpectrum(fig.add_subplot(), spectra, spectrumSettings(**settings))
    return _png(fig)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


def _aggFigure(width, height, dpi):
    """A figure drawn with matplotlib's Agg renderer directly, not a pyplot figure"""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(width, height), dpi=dpi, layout="constrained")
    FigureCanvasAgg(fig)
    return fig


def _histogram(data, bincount):
    """Accept a Histogram (or a Datum holding one), or make one from an ImageCube or a Datum holding one"""
    from pcot.datum import Datum
    from pcot.imagecube import ImageCube
    from pcot.utils.histogram import Histogram
    if isinstance(data, Datum) and data.tp == Datum.HISTOGRAM:
        data = data.get(Datum.HISTOGRAM)
    if isinstance(data, Histogram):
        if bincount is not None:
            raise TypeError("bincount can only be given when plotting an image, not a Histogram")
        return data
    if isinstance(data, (ImageCube, Datum)):
        return Histogram.fromImage(data, 16 if bincount is None else bincount)
    raise TypeError(f"expected a Histogram, an ImageCube or a Datum holding either, not {type(data).__name__}")


def histogram(data, ax=None, bincount: Optional[int] = None):
    """Plot histograms of the bands of an image as the histogram node does, and return the matplotlib Axes.

    * data - a Histogram (or a Datum holding one, such as a histogram node's output), or an image (an
      ImageCube or a Datum holding one) to make one from: only pixels in the image's ROIs are counted, if
      it has any, and BAD pixels are not counted
    * ax - matplotlib Axes to draw on; if None, a new figure is created
    * bincount - the number of bins when plotting an image (default 16)
    """
    from pcot.plotting.histogramplot import plotHistogram
    hist = _histogram(data, bincount)
    ax = _newAxes(ax)
    plotHistogram(ax, hist)
    return ax


def histogramFromNode(node, ax=None):
    """Plot a histogram node's histograms as the node's own plot shows them, and return the matplotlib
    Axes. The document must have been run."""
    if node.type.name != "histogram":
        raise TypeError(f"'{node.displayName}' is a {node.type.name} node, not a histogram node")
    if node.data is None:
        raise ValueError(f"histogram node '{node.displayName}' has no data - has the document been run?")
    return histogram(node.data, ax)


def histogramPNG(data, width=8, height=4.5, dpi=100, bincount: Optional[int] = None) -> bytes:
    """Plot histograms (a Histogram, or of an image) and return the plot as PNG data. Uses matplotlib's Agg
    renderer directly, so it doesn't create a pyplot figure."""
    from pcot.plotting.histogramplot import plotHistogram
    hist = _histogram(data, bincount)
    fig = _aggFigure(width, height, dpi)
    plotHistogram(fig.add_subplot(), hist)
    return _png(fig)
