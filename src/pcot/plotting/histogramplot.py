"""
Drawing histogram plots onto matplotlib axes. This is the code behind the histogram node's plot, kept free
of Qt so that library and notebook users can draw the same plots (see pcot.plotting.histogram).

Nothing here may import pcot.ui.mplwidget, which switches matplotlib to its Qt backend.
"""

import matplotlib


def plotHistogram(ax, hist):
    """Draw a Histogram onto a matplotlib Axes, clearing it first: a translucent bar chart for each band"""
    ax.cla()  # clear any previous plot
    cols = matplotlib.colormaps['Dark2'].colors
    for i, (lab, counts) in enumerate(zip(hist.labels, hist.counts)):
        ax.hist(hist.edges[:-1], hist.edges, weights=counts, alpha=0.34, label=lab,
                color=cols[i % len(cols)])
    ax.legend()
