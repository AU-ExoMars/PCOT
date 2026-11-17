"""
Drawing spectrum plots onto matplotlib axes. This is the code behind the spectrum node's plot, kept free
of Qt so that library and notebook users can draw the same plots (see pcot.plotting.spectrum).

Nothing here may import pcot.ui.mplwidget, which switches matplotlib to its Qt backend.
"""

import math
import warnings
from typing import Callable, Iterable, List, Optional

import matplotlib
import numpy as np

from pcot.cameras.filters import wav2RGB

# short names for error bar modes used in the dialog, in the same order as they appear there
errorBarModes = ["none", "stderror", "stddev"]

# short names for colour modes used in the dialog
colourModes = ["fromROIs", "scheme1", "scheme2"]

# short names for bandwidth modes used in the dialog
bandwidthModes = ["none", "errorbar", "vertbar"]

# short names for wavelength annotation modes used in the dialog
annotateModes = ["none", "line", "linefwhm"]

# wavelength units and scaling factors to convert to them from nm and the string for that annotation
# in the "wavelength (string)" x-axis label
wavelengthUnits = {
    "nm": (1, "nm"),
    "microns": (1e-3, "$\\mu$m"),
}


def orderLegends(sortlist: Iterable[str], legends: Iterable[str]) -> List[str]:
    """Return the legends in plotting order: those in the sort list first, in its order, then any others.
    Sort list entries which aren't in the legends are dropped."""
    legends = list(legends)
    order = [x for x in sortlist if x in legends]
    order.extend([x for x in legends if x not in order])
    return order


def plotSpectrum(ax, spectra, params, order: Optional[List[str]] = None,
                 onError: Optional[Callable[[str], None]] = None):
    """Draw a set of spectra onto a matplotlib Axes, clearing it first.

    * ax - the Axes to draw on
    * spectra - a SpectrumSet (a mapping of legend to Spectrum)
    * params - the plot settings: a spectrum node's params TaggedDict (its sortlist is not used)
    * order - the legends in the order to plot and stack them; all of them if None, in the set's order
    * onError - called with a message when some data can't be plotted; by default a warning is issued
    """
    if onError is None:
        def onError(msg):
            warnings.warn(msg, stacklevel=3)
    if order is None:
        order = list(spectra.keys())

    ax.cla()  # clear any previous plot

    # pick a colour scheme for multiple plots if we're not getting the colour
    # from the ROIs
    if params.colourmode == "scheme2":
        cols = matplotlib.colormaps['tab10'].colors
    else:
        cols = matplotlib.colormaps['Dark2'].colors

    # get the scale factor for the x-units we've chosen and the symbol to use
    # on the axis label
    unit_scale_factor, symbol = wavelengthUnits[params.wavelength_units]

    # the dict consists of a list of channel data tuples for each image/roi.
    colidx = 0
    stackSep = params.stackSep / 20

    if stackSep != 0:  # turn off tick labels if we are stacking; the Y values would be deceptive.
        ax.set_yticklabels('')

    ax.tick_params(axis='both', labelsize=params.axisFontSize)
    ax.set_xlabel(f"wavelength ({symbol})", fontsize=params.labelFontSize)
    ax.set_ylabel(params.y_label if stackSep == 0 else f"{params.y_label} (stacked)",
                  fontsize=params.labelFontSize)

    stackpos = 0
    for legend in order:
        unfiltered = spectra[legend]

        # filter out any "masked" means - those are from regions which are entirely DQ BAD in a channel.
        # These also seem to show up as None sometimes, so we have to check for that too.

        x = {filt: spec for filt, spec in unfiltered.values.items() if spec.v is not None and
             spec.v.n is not np.ma.masked}

        if len(x) == 0:
            onError(f"No points have good data for point {legend}")
            continue
        if len(x) != len(unfiltered.values):
            onError(f"Some points have bad data for point {legend}")

        # get a list of the filters (the dict keys) sorted by filter cwl
        filters = sorted(x.keys(), key=lambda ff: ff.cwl)

        # extract data from the dictionary
        values = [x[filt] for filt in filters]
        means = [a.v.n for a in values]
        sds = [a.v.u for a in values]
        counts = [a.samples for a in values]

        # spectra which didn't come from images (e.g. from a spectrometer) may not have a colour
        if params.colourmode == 'fromROIs' and unfiltered.colour is not None:
            col = unfiltered.colour
        else:
            col = cols[colidx % len(cols)]
        means = [x + stackSep * stackpos for x in means]

        wavelengths = [x.cwl * unit_scale_factor for x in filters]

        ax.plot(wavelengths, means, c=col, label=legend)
        ax.scatter(wavelengths, means, c=[wav2RGB(x.cwl) for x in filters], s=0)
        if params.fixedYAxis:
            ax.set_ylim(0, 1)

        if params.annotate != 'none':
            # full height of the plot, regardless of the y-axis limits - so we use the
            # x-axis transform, which keeps x in data coordinates but y in axes fraction (0-1).
            ax.vlines(wavelengths, 0, 1, transform=ax.get_xaxis_transform(),
                      colors='grey', linewidth=0.5, zorder=0)
            for wl in wavelengths:
                ax.annotate(f"{wl:g}", xy=(wl, 0),
                            xycoords=('data', 'axes fraction'),
                            xytext=(3, 3), textcoords='offset points',
                            rotation=90, ha='left', va='bottom',
                            fontsize=params.axisFontSize)
            if params.annotate == 'linefwhm':
                for f in filters:
                    a = f.cwl - f.fwhm / 2
                    b = f.cwl + f.fwhm / 2
                    ax.axvspan(a * unit_scale_factor, b * unit_scale_factor,
                               color='lightgrey', alpha=0.3, zorder=0)

        if params.errorbarmode != 'none':
            # calculate standard errors from standard deviations
            stderrs = [std / math.sqrt(count) for std, count in zip(sds, counts)]
            ax.errorbar(wavelengths, means,
                        stderrs if params.errorbarmode == 'stderror' else sds,
                        # only show the x error bar if we are in the correct bandwidth mode
                        xerr=[x.fwhm / 2 * unit_scale_factor for x in filters] if params.bandwidthmode == 'errorbar' else None,
                        ls="None", capsize=4, c=col)
        colidx += 1
        # subtraction to make the plots stack the same way as the legend!
        stackpos -= params.stackSep

        # now show the bandwidth as a vertical span if we are in the correct mode
        if params.bandwidthmode == 'vertbar':
            for f in filters:
                ax.axvspan((f.cwl - f.fwhm / 2) * unit_scale_factor,
                           (f.cwl + f.fwhm / 2) * unit_scale_factor, color=col, alpha=0.1)

    ax.legend(fontsize=params.legendFontSize)
    ymin, ymax = ax.get_ylim()
    ymin = ymin - params.bottomSpace / 10
    if ymax - ymin < 0.01:  # if the y range is too small, expand it
        ymin -= 0.01
        ymax += 0.01
    ax.set_ylim(ymin, ymax)
    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin, xmax + params.rightSpace * 100 * unit_scale_factor)

    if params.stackSep == 0:  # only remove negative ticks if we're labelling the ticks.
        ax.set_yticks([x for x in ax.get_yticks() if x >= 0])
