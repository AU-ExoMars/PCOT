"""
Tests for drawing reflectance calibration plots outside the PCOT application (pcot.plotting), as used from
scripts and Jupyter notebooks. The plots themselves are the reflectance node's; these tests check the library
interface.
"""
import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest
from matplotlib.figure import Figure

import pcot
import pcot.plotting
from pcot.calib.fit import CalibrationData
from pcot.datum import Datum
from pcot.document import Document

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GRAPH = Path(__file__).parent.parent / "graphs" / "testreflbasic.pcot"
FILTERS = ['G01', 'G03', 'G04', 'G05', 'G06']


def run_node():
    """Run the test graph and return its reflectance node, whose data has 5 filters with 5 points each"""
    pcot.setup()
    doc = Document(str(GRAPH))
    doc.run()
    node = doc.graph.getByDisplayName("reflectance")[0]
    assert node.data.filters == FILTERS
    return node


def new_axes():
    return Figure().add_subplot()


def legend_texts(ax):
    return [t.get_text() for t in ax.get_legend().get_texts()]


def test_all_filters():
    """All filters are plotted on one set of axes, each with its fit line and a legend entry"""
    data = run_node().data
    ax = new_axes()
    assert pcot.plotting.reflectance(data, ax) is ax
    assert legend_texts(ax) == ["G01 440nm", "G03 530nm", "G04 570nm", "G05 610nm", "G06 670nm"]
    assert len(ax.lines) >= 5   # fit lines (and error bar lines)
    assert ax.get_xlabel() == "Known reflectance" and ax.get_ylabel() == "Measured reflectance"
    assert ax.get_title() == ""


def test_single_filter():
    """A single filter's plot has its fit as the title, and its points can be labelled with their patches"""
    data = run_node().data
    ax = pcot.plotting.reflectance(data, new_axes(), filters="G04")
    fit = data.fits["G04"]
    assert ax.get_title() == f"Fit for G04 570: m={fit.m:0.3f}, c={fit.c:0.3f}"
    assert ax.get_legend() is None
    assert len(ax.texts) == 5
    ax = pcot.plotting.reflectance(data, new_axes(), filters=["G04"], show_patches=False)
    assert len(ax.texts) == 0


def test_some_filters_and_unknown_filters():
    data = run_node().data
    ax = pcot.plotting.reflectance(data, new_axes(), filters=["G06", "G01"])
    assert legend_texts(ax) == ["G06 670nm", "G01 440nm"]
    with pytest.raises(ValueError, match="not in the calibration data: G99"):
        pcot.plotting.reflectance(data, new_axes(), filters=["G01", "G99"])


def test_accepts_datum_and_rejects_others():
    node = run_node()
    out = node.getOutputDatum(2)
    assert out.tp == Datum.CALIBRATION
    assert len(legend_texts(pcot.plotting.reflectance(out, new_axes()))) == 5
    with pytest.raises(TypeError):
        pcot.plotting.reflectance(node.getOutputDatum(0), new_axes())    # m, a number
    with pytest.raises(TypeError):
        pcot.plotting.reflectance("hello", new_axes())


def test_missing_points_are_reported():
    """A filter with no fit is left out of the plot, with a warning"""
    data = run_node().data
    data = dataclasses.replace(data, fits={k: v for k, v in data.fits.items() if k != "G03"})
    with pytest.warns(UserWarning, match="No fit data for filter G03"):
        ax = pcot.plotting.reflectance(data, new_axes())
    assert "G03 530nm" not in legend_texts(ax)


def test_per_filter():
    """Separate plots give a grid of small plots, one per filter, titled with their fits"""
    data = run_node().data
    fig = Figure()
    assert pcot.plotting.reflectancePerFilter(data, fig) is fig
    assert len(fig.axes) == 5
    assert [ax.get_subplotspec().get_geometry()[:2] for ax in fig.axes] == [(2, 3)] * 5
    assert fig.axes[1].get_title().startswith("Fit for G03 530: m=")
    pcot.plotting.reflectancePerFilter(data, fig, columns=5)     # clears the figure first
    assert len(fig.axes) == 5
    assert fig.axes[0].get_subplotspec().get_geometry()[:2] == (1, 5)


def test_from_node():
    """A reflectance node's plot follows its filter, patch and separate plot settings"""
    node = run_node()
    fig = pcot.plotting.reflectanceFromNode(node, Figure())
    assert len(fig.axes) == 1 and len(legend_texts(fig.axes[0])) == 5

    node.filter_to_plot = "G05"
    node.params.show_patches = False
    fig = pcot.plotting.reflectanceFromNode(node, fig)
    assert len(fig.axes) == 1
    assert fig.axes[0].get_title().startswith("Fit for G05") and len(fig.axes[0].texts) == 0

    node.params.sep_plots = True
    assert len(pcot.plotting.reflectanceFromNode(node, fig).axes) == 5

    other = next(n for n in node.graph.nodes if n.type.name != "reflectance")
    with pytest.raises(TypeError, match="not a reflectance node"):
        pcot.plotting.reflectanceFromNode(other, Figure())


def test_not_run():
    pcot.setup()
    doc = Document()
    node = doc.graph.create("reflectance")
    with pytest.raises(ValueError, match="has the document been run"):
        pcot.plotting.reflectanceFromNode(node, Figure())


def test_display_in_notebooks():
    """Calibration data displays as a plot; empty calibration data displays as text"""
    node = run_node()
    assert node.data._repr_png_().startswith(PNG_SIGNATURE)
    assert node.getOutputDatum(2)._repr_png_().startswith(PNG_SIGNATURE)
    assert pcot.plotting.reflectancePNG(node.data, filters="G01").startswith(PNG_SIGNATURE)
    assert CalibrationData()._repr_png_() is None


def test_plotting_keeps_matplotlib_backend():
    """Reflectance plotting must not import the GUI's plot widget, which switches matplotlib to its Qt
    backend and would stop notebooks showing plots inline. Run separately, as other tests may import it."""
    code = ("import sys, matplotlib; matplotlib.use('Agg'); import pcot; pcot.setup(); "
            "import pcot.plotting; from pcot.document import Document; "
            f"doc = Document({str(GRAPH)!r}); doc.run(); "
            "node = doc.graph.getByDisplayName('reflectance')[0]; "
            "pcot.plotting.reflectance(node.data); pcot.plotting.reflectancePerFilter(node.data); "
            "pcot.plotting.reflectanceFromNode(node); node.data._repr_png_(); "
            "print(matplotlib.get_backend(), 'pcot.ui.mplwidget' in sys.modules)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1].lower() == "agg false"
