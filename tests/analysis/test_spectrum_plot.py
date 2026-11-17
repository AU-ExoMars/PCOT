"""
Tests for drawing spectrum plots outside the PCOT application (pcot.plotting), as used from scripts and
Jupyter notebooks. The plots themselves are the spectrum node's; these tests check the library interface.
"""
import subprocess
import sys

import matplotlib
import pytest
from matplotlib.figure import Figure

import pcot
import pcot.plotting
from pcot.datum import Datum
from pcot.document import Document
from pcot.rois import ROICircle
from pcot.utils.spectrumdata import SpectrumSet

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def make_spectra():
    """A set of two spectra, 'left' and 'right', from ROIs on a three-band generated image"""
    pcot.setup()
    doc = Document()
    node = doc.graph.create("gen")
    node.params.imgwidth, node.params.imgheight = 64, 64
    node.params.chans.append_default().set(2, 10, 100, "gradient-x")
    node.params.chans.append_default().set(3, 20, 200, "gradient-y")
    node.params.chans.append_default().set(25, 0, 300, "checkx")
    doc.run()
    img = node.getOutput(0, Datum.IMG)
    img.rois.append(ROICircle(15, 30, 6, label="left"))
    img.rois.append(ROICircle(45, 30, 6, label="right"))
    return SpectrumSet.fromImages({"in": img})


def new_axes():
    return Figure().add_subplot()


def legend_texts(ax):
    return [t.get_text() for t in ax.get_legend().get_texts()]


def test_spectrum_draws_each_spectrum():
    """Each spectrum is a labelled line with a point per band"""
    ss = make_spectra()
    ax = new_axes()
    assert pcot.plotting.spectrum(ss, ax) is ax
    lines = [x for x in ax.get_lines() if not x.get_label().startswith("_")]
    assert sorted(x.get_label() for x in lines) == sorted(ss.keys())
    assert all(len(x.get_xdata()) == 3 for x in lines)
    assert ax.get_xlabel() == "wavelength (nm)"


def test_spectrum_accepts_datum():
    ss = make_spectra()
    ax = pcot.plotting.spectrum(Datum(Datum.SPECTRA, ss, ss.getSources()), new_axes())
    assert len(legend_texts(ax)) == len(ss.keys())


def test_spectrum_order():
    """Spectra named in the order come first, in that order, then the rest"""
    ss = make_spectra()
    names = list(ss.keys())
    last = names[-1]
    ax = pcot.plotting.spectrum(ss, new_axes(), order=[last])
    assert legend_texts(ax)[0] == last


def test_spectrum_settings():
    """Plot settings are the spectrum node's, and change the plot"""
    ss = make_spectra()
    ax = pcot.plotting.spectrum(ss, new_axes(), wavelength_units="microns", y_label="DN")
    assert ax.get_xlabel() == "wavelength ($\\mu$m)"
    assert ax.get_ylabel() == "DN"


def test_spectrum_bad_settings():
    ss = make_spectra()
    with pytest.raises(TypeError, match="not a spectrum plot setting"):
        pcot.plotting.spectrum(ss, new_axes(), colour="red")
    with pytest.raises(TypeError, match="not a spectrum plot setting"):
        pcot.plotting.spectrum(ss, new_axes(), sortlist=["a"])    # node setting, not a plot option
    with pytest.raises(ValueError):
        pcot.plotting.spectrum(ss, new_axes(), errorbarmode="huge")


def test_spectrum_rejects_other_data():
    with pytest.raises(TypeError):
        pcot.plotting.spectrum(Datum(Datum.STRING, "hello", pcot.sources.nullSourceSet), new_axes())


def test_spectrum_from_node():
    """A spectrum node's plot uses the node's own settings and order"""
    pcot.setup()
    doc = Document()
    gen = doc.graph.create("gen")
    gen.params.chans.append_default().set(2, 10, 100, "gradient-x")
    gen.params.chans.append_default().set(3, 20, 200, "gradient-y")
    roi = doc.graph.create("circle")
    roi.connect(0, gen, 0)
    roi.roi.set(20, 20, 5)
    spec = doc.graph.create("spectrum")
    spec.connect(0, roi, 0)
    spec.connect(1, gen, 0)
    with pytest.raises(ValueError, match="has the document been run"):
        pcot.plotting.spectrumFromNode(spec, new_axes())
    doc.run()
    spec.params.y_label = "from node"
    names = list(spec.data.keys())
    spec.params.sortlist.set(list(reversed(names)))
    ax = pcot.plotting.spectrumFromNode(spec, new_axes())
    assert ax.get_ylabel() == "from node"
    assert legend_texts(ax) == list(reversed(names))
    with pytest.raises(TypeError, match="not a spectrum node"):
        pcot.plotting.spectrumFromNode(gen, new_axes())


def test_spectra_display_in_notebooks():
    """SpectrumSets, and Datums holding them, give PNG data for notebooks to display"""
    ss = make_spectra()
    assert ss._repr_png_().startswith(PNG_SIGNATURE)
    assert Datum(Datum.SPECTRA, ss, ss.getSources())._repr_png_().startswith(PNG_SIGNATURE)


def test_plotting_keeps_matplotlib_backend():
    """Plotting must not import the GUI's plot widget, which switches matplotlib to its Qt backend and
    would stop notebooks showing plots inline. Run separately, as other tests may import the widget."""
    code = ("import sys, matplotlib; matplotlib.use('Agg'); import pcot; pcot.setup(); "
            "import pcot.plotting; from tests_helper_spectra import make; "
            "pcot.plotting.spectrum(make()); make()._repr_png_(); "
            "print(matplotlib.get_backend(), 'pcot.ui.mplwidget' in sys.modules)")
    helper = ("import pcot\nfrom pcot.document import Document\nfrom pcot.datum import Datum\n"
              "from pcot.rois import ROICircle\nfrom pcot.utils.spectrumdata import SpectrumSet\n"
              "def make():\n"
              "    doc = Document(); n = doc.graph.create('gen')\n"
              "    n.params.chans.append_default().set(2, 10, 100, 'gradient-x')\n"
              "    n.params.chans.append_default().set(3, 20, 200, 'gradient-y')\n"
              "    doc.run(); img = n.getOutput(0, Datum.IMG)\n"
              "    img.rois.append(ROICircle(20, 20, 5, label='a'))\n"
              "    return SpectrumSet.fromImages({'in': img})\n")
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "tests_helper_spectra.py"), "w") as f:
            f.write(helper)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([d, os.environ.get("PYTHONPATH", "")]))
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                timeout=300, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1].lower() == "agg false"
