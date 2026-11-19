"""
Drawing reflectance calibration plots - measured against known reflectance for each filter, with the fitted
line - onto matplotlib axes or figures. This is the code behind the reflectance node's plot, kept free of Qt
so that library and notebook users can draw the same plots (see pcot.plotting.reflectance).

Nothing here may import pcot.ui.mplwidget, which switches matplotlib to its Qt backend.
"""

import dataclasses
import warnings
from typing import Callable, List, Optional


def _defaultOnMessage(msg):
    warnings.warn(msg, stacklevel=3)


def setReflectanceAxes(ax, separate=False):
    """Clear a set of axes and set them up for a reflectance plot, with the axes passing through the origin.
    Separate (small, per-filter) plots have smaller tick labels and no axis labels."""
    ax.cla()
    if not separate:
        ax.set_xlabel("Known reflectance")
        ax.set_ylabel("Measured reflectance")
    else:
        ax.tick_params(labelsize=6)

    # move the axes to pass through the origin
    ax.spines['left'].set_position('zero')
    ax.spines['right'].set_color('none')
    ax.yaxis.tick_left()
    ax.spines['bottom'].set_position('zero')
    ax.spines['top'].set_color('none')
    ax.xaxis.tick_bottom()


def _pointsAndFit(data, filt, onMessage):
    """Get the points (as separate lists) and fit for a filter, or None if either is missing"""
    # these may be None if the calibration failed before they were set
    points = (data.points_per_filter or {}).get(filt, None)
    fit = (data.fits or {}).get(filt, None)
    if points is None:
        onMessage(f"No points of data for filter {filt}")
        return None
    if fit is None:
        onMessage(f"No fit data for filter {filt}")
        return None
    points = [dataclasses.astuple(p) for p in points]
    known, measured, sample_counts, patches = zip(*points)
    return ([x.mean for x in known], [x.std for x in known],
            [x.mean for x in measured], [x.std for x in measured],
            sample_counts, patches, fit)


def plotReflectance(ax, data, filters: Optional[List[str]] = None, show_patches=True,
                    onMessage: Optional[Callable[[str], None]] = None):
    """Draw the points and fits for some or all of the filters in a CalibrationData onto one set of axes,
    clearing them first. A single filter is given a title with its fit, and its points can be labelled
    with their patches and measured values.

    * ax - the Axes to draw on
    * data - a CalibrationData
    * filters - the names of the filters to plot, or None for all of them
    * show_patches - label the points with their patches and measured values, if plotting one filter
    * onMessage - called with a message when a filter can't be plotted; by default a warning is issued
    """
    if onMessage is None:
        onMessage = _defaultOnMessage
    setReflectanceAxes(ax)

    cwls = data.cwls or {}      # may be None if the calibration failed early
    bands = (data.filters or []) if filters is None else filters

    col = 0  # colour index
    for band in bands:
        pf = _pointsAndFit(data, band, onMessage)
        if pf is None:
            continue
        known_mean, known_std, measured_mean, measured_std, sample_counts, patches, fit = pf

        colname = f"C{col}"
        col += 1
        if fit:
            ax.axline((0, fit.c), slope=fit.m, color=colname)
        cwl = cwls.get(band, 0)
        ax.errorbar(known_mean, measured_mean, yerr=measured_std, xerr=known_std,
                    label=f"{band} {int(cwl)}nm", fmt='x',
                    color=colname)

        # point labelling and title : don't do this if we're plotting all bands or it's turned off
        if len(bands) == 1:
            ax.set_title(f"Fit for {band} {int(cwl)}: m={fit.m:0.3f}, c={fit.c:0.3f}")
            if show_patches:
                for i, patch in enumerate(patches):
                    # plot the patch name and the measured value at the point
                    ax.annotate(f"{patch}\n{measured_mean[i]:.2f}±{measured_std[i]:.2f} (n={sample_counts[i]})",
                                (known_mean[i], measured_mean[i]), fontsize=8)

    if len(bands) > 1:
        ax.legend(loc="lower right")


def plotReflectancePerFilter(fig, data, onMessage: Optional[Callable[[str], None]] = None, columns=3):
    """Clear a matplotlib Figure and draw a small plot of the points and fit for each filter in a
    CalibrationData onto it, in a grid with the given number of columns. Returns the list of axes."""
    if onMessage is None:
        onMessage = _defaultOnMessage
    fig.clf()
    filters = data.filters or []    # may be None if the calibration failed early
    cwls = data.cwls or {}
    plotcount = len(filters)
    rows = ((plotcount - 1) // columns) + 1
    cols = min(columns, plotcount)

    axes = []
    for plotidx, filt in enumerate(filters):
        # add_subplot args: rows in entire plot, cols in plot, index of the plot we're making (1-based).
        ax = fig.add_subplot(rows, cols, plotidx + 1)
        axes.append(ax)
        setReflectanceAxes(ax, separate=True)

        pf = _pointsAndFit(data, filt, onMessage)
        if pf is None:
            continue
        known_mean, known_std, measured_mean, measured_std, sample_counts, patches, fit = pf

        if fit:
            ax.axline((0, fit.c), slope=fit.m)
        ax.errorbar(known_mean, measured_mean, yerr=measured_std, xerr=known_std, label=filt, fmt='x')

        cwl = cwls.get(filt, 0)
        ax.set_title(f"Fit for {filt} {int(cwl)}: m={fit.m:0.3f}, c={fit.c:0.3f}", fontsize=6)
        for i, patch in enumerate(patches):
            # plot the patch name and the measured value at the point
            ax.annotate(f"{patch}\n{measured_mean[i]:.2f}±{measured_std[i]:.2f}",
                        (known_mean[i], measured_mean[i]), fontsize=5)
    return axes
