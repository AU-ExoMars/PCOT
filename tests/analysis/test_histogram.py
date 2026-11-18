"""
Tests for histograms of images (pcot.utils.histogram.Histogram), made by the histogram node and usable
directly from scripts and Jupyter notebooks, and for plotting them (pcot.plotting.histogram).
"""
import subprocess
import sys

import numpy as np
import pytest
from matplotlib.figure import Figure

import pcot
import pcot.dq
import pcot.plotting
from pcot.datum import Datum
from pcot.document import Document
from pcot.cameras.filters import Filter
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource, Source
from pcot.rois import ROICircle, ROIRect
from pcot.utils.histogram import Histogram

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def make_image():
    """A 3-band 10x8 image: band i is all i*0.1 except one pixel, which is 1"""
    pcot.setup()
    data = np.zeros((8, 10, 3), dtype=np.float32)
    for i in range(3):
        data[:, :, i] = i * 0.1
        data[i, i, i] = 1
    return ImageCube(data)


def new_axes():
    return Figure().add_subplot()


def test_counts_and_bins():
    """Every band is counted over the same bins, spanning the whole image's range"""
    h = Histogram.fromImage(make_image(), 10)
    assert len(h) == 3 and h.bincount == 10
    assert h.counts.shape == (3, 10)
    assert h.edges[0] == 0 and h.edges[-1] == 1
    assert (h.counts.sum(axis=1) == 80).all()
    assert h.counts[0, 0] == 79 and h.counts[1, 1] == 79 and h.counts[2, 2] == 79
    assert (h.counts[:, -1] == 1).all()   # the 1s in each band


def test_roi_and_bad_pixels():
    """Only pixels in the ROI are counted, and BAD pixels in a band aren't counted for that band"""
    img = make_image()
    img.rois.append(ROIRect(rect=(0, 0, 5, 4)))   # 20 pixels, including all the 1s
    img.dq[0, 0, 0] |= pcot.dq.NODATA             # band 0's 1
    img.dq[3, 3, 1] |= pcot.dq.SAT                # an ordinary pixel in band 1
    h = Histogram.fromImage(img, 10)
    assert list(h.counts.sum(axis=1)) == [19, 19, 20]
    assert h.counts[0, -1] == 0 and h.counts[1, -1] == 1


def test_range_only_covers_counted_pixels():
    """The bins span only the pixels which are counted: BAD pixels, and pixels in the ROI's bounding box
    but not in the ROI, don't stretch the range"""
    img = make_image()
    img.rois.append(ROICircle(4, 4, 3))       # bounding box (1,1)-(7,7); its corners are outside the circle
    img.img[1, 1, 0] = 100                    # in the bounding box, not in the ROI
    img.img[4, 4, 0] = 50                     # in the ROI, but BAD
    img.dq[4, 4, 0] |= pcot.dq.NODATA
    img.img[4, 5, 1] = np.nan                 # BAD pixels may hold anything
    img.dq[4, 5, 1] |= pcot.dq.DIVZERO
    img.img[2, 2, 2] = 0.2                    # make_image's 1 in this band is inside the ROI
    img.img[3, 4, 2] = 0.8                    # the largest counted value
    h = Histogram.fromImage(img, 8)
    assert h.edges[0] == 0 and h.edges[-1] == np.float32(0.8)
    assert np.isfinite(h.counts).all()


def test_no_counted_pixels():
    """If every pixel is BAD, nothing is counted, over a range of 0-1"""
    img = make_image()
    img.img[0, 0, 0] = np.nan
    img.dq |= pcot.dq.NODATA
    h = Histogram.fromImage(img, 4)
    assert (h.counts == 0).all()
    assert h.edges[0] == 0 and h.edges[-1] == 1


def test_single_band_and_constant_image():
    """A single band image works, and an image of one value still gets distinct bins (as np.histogram
    gives them), centred on the value"""
    pcot.setup()
    h = Histogram.fromImage(ImageCube(np.full((4, 4), 0.5, dtype=np.float32)), 4)
    assert h.counts.shape == (1, 4)
    assert len(set(h.edges)) == 5
    assert h.edges[0] == 0 and h.edges[-1] == 1
    assert h.counts.sum() == 16


def test_accepts_datum():
    img = make_image()
    h = Histogram.fromImage(Datum(Datum.IMG, img), 10)
    assert (h.counts == Histogram.fromImage(img, 10).counts).all()
    with pytest.raises(TypeError):
        Histogram.fromImage(Datum(Datum.STRING, "hello", pcot.sources.nullSourceSet))


def sourced_image(bands):
    """A 4x4 image with a band for each (input index, filter cwl or None, band value) in bands"""
    pcot.setup()
    data = np.stack([np.full((4, 4), v, dtype=np.float32) for _, _, v in bands], axis=-1)
    sources = MultiBandSource([Source().setInputIdx(i).setBand(Filter(cwl, 10) if cwl else "X")
                               for i, cwl, _ in bands])
    return ImageCube(data, sources=sources)


def test_band_labels():
    """Bands are labelled by wavelength where they have a single filter; bands without one, or sharing a
    wavelength, by their sources; and if those clash too, with the band index added"""
    assert Histogram.fromImage(sourced_image([(0, 440, 0), (0, 438.5, 1)])).labels == ["440", "438.5"]
    assert Histogram.fromImage(sourced_image([(0, 440, 0), (1, 440, 1), (0, 530, 2)])).labels ==         ["0:440", "1:440", "530"]
    assert Histogram.fromImage(sourced_image([(0, 440, 0), (0, None, 1)])).labels == ["440", "0:X"]
    assert Histogram.fromImage(sourced_image([(0, 440, 0), (0, 440, 1)])).labels == ["0:440 #0", "0:440 #1"]
    # bands with no sources at all
    assert Histogram.fromImage(make_image()).labels == ["band 0", "band 1", "band 2"]


def test_labels_must_be_unique():
    with pytest.raises(ValueError, match="unique"):
        Histogram(["a", "a"], [[1], [2]], [0, 1])
    with pytest.raises(ValueError, match="unique"):
        Histogram(["lower"], [[1]], [0, 1])


def test_table():
    """As a table, there is a row for each bin, with its lower and upper edges, and a column of counts for
    each band"""
    h = Histogram.fromImage(make_image(), 4)
    p = h.tabularProvider()
    assert p.getHeaders() == ["lower", "upper"] + h.labels
    rows = list(p)
    assert [r["lower"] for r in rows] == ["0", "0.25", "0.5", "0.75"]
    assert [r["upper"] for r in rows] == ["0.25", "0.5", "0.75", "1"]
    assert [r[h.labels[1]] for r in rows] == ["79", "0", "0", "1"]
    d = Datum(Datum.HISTOGRAM, h, h.getSources())
    assert d.tabularProvider().csvString() == p.csvString() == str(h)


def test_narrow_bin_edges():
    """Bin edges are given to the configured significant figures (5 in tests), or more if needed to tell
    them apart; large values aren't put into scientific notation"""
    p = Histogram(["a"], [[1, 2, 3]], np.array([1000.0, 1000.001, 1000.002, 1000.003], dtype=np.float32))         .tabularProvider()
    rows = list(p)
    lowers = [r["lower"] for r in rows] + [rows[-1]["upper"]]
    assert len(set(lowers)) == 4
    assert lowers[0] == "1000"
    assert all("e" not in x for x in lowers)
    rows = list(Histogram(["a"], [[1]], np.array([0, 123456.7], dtype=np.float32)).tabularProvider())
    assert rows[0]["upper"] == "123457"


def test_serialisation():
    """Histogram data survives serialisation exactly, with its sources"""
    img = make_image()
    img.rois.append(ROIRect(rect=(0, 0, 5, 4)))
    h = Histogram.fromImage(img, 7)
    d = Datum(Datum.HISTOGRAM, h, h.getSources())
    name, data = d.serialise()
    d2 = Datum.HISTOGRAM.deserialise(data)
    h2 = d2.get(Datum.HISTOGRAM)
    assert h2.labels == h.labels
    assert (h2.counts == h.counts).all()
    assert h2.edges.dtype == np.float32 and (h2.edges == h.edges).all()
    assert d2.getSources().serialise() == d.getSources().serialise()
    assert h2.getSources() is d2.getSources()


def test_node_stores_histogram():
    """The histogram node keeps its histograms, using the document's band captions, and outputs them with the
    image's sources; with no input it has neither"""
    pcot.setup()
    doc = Document()
    gen = doc.graph.create("gen")
    gen.params.chans.append_default().set(0.5, 0.1, 440, "gaussian")
    gen.params.chans.append_default().set(1, 0, 540, "rand")
    node = doc.graph.create("histogram")
    node.connect(0, gen, 0)
    node.params.bincount = 12
    doc.run()
    assert isinstance(node.hist, Histogram)
    assert node.hist.bincount == 12
    assert node.hist.labels == ["440", "540"]
    out = node.getOutputDatum(0)
    assert out.tp == Datum.HISTOGRAM and out.get(Datum.HISTOGRAM) is node.hist
    assert out.getSources().serialise() == gen.getOutputDatum(0).getSources().serialise()
    assert len(pcot.plotting.histogram(out, new_axes()).patches) == 24

    ax = pcot.plotting.histogramFromNode(node, new_axes())
    assert [t.get_text() for t in ax.get_legend().get_texts()] == node.hist.labels
    with pytest.raises(TypeError, match="not a histogram node"):
        pcot.plotting.histogramFromNode(gen, new_axes())

    node.disconnect(0)
    doc.run()
    assert node.hist is None
    assert node.getOutputDatum(0) is None or node.getOutputDatum(0).isNone()
    with pytest.raises(ValueError, match="has the document been run"):
        pcot.plotting.histogramFromNode(node, new_axes())


def test_plotting():
    """Histograms, images and Datums holding images can be plotted; bincount only goes with images"""
    img = make_image()
    h = Histogram.fromImage(img, 10)
    ax = new_axes()
    assert pcot.plotting.histogram(h, ax) is ax
    assert len(ax.patches) == 30                           # a bar per bin per band
    assert [t.get_text() for t in ax.get_legend().get_texts()] == h.labels
    assert h.plot(ax) is ax and len(ax.patches) == 30      # clears first
    assert len(pcot.plotting.histogram(img, new_axes(), bincount=5).patches) == 15
    assert len(pcot.plotting.histogram(Datum(Datum.IMG, img), new_axes()).patches) == 48   # default 16
    with pytest.raises(TypeError, match="bincount"):
        pcot.plotting.histogram(h, new_axes(), bincount=5)
    with pytest.raises(TypeError):
        pcot.plotting.histogram("hello", new_axes())


def test_display_in_notebooks():
    h = Histogram.fromImage(make_image())
    assert h._repr_png_().startswith(PNG_SIGNATURE)
    assert pcot.plotting.histogramPNG(make_image(), bincount=4).startswith(PNG_SIGNATURE)
    assert "3 bands, 16 bins" in repr(h)


def test_plotting_keeps_matplotlib_backend():
    """Histogram plotting must not import the GUI's plot widget, which switches matplotlib to its Qt
    backend and would stop notebooks showing plots inline. Run separately, as other tests may import it."""
    code = ("import sys, numpy as np, matplotlib; matplotlib.use('Agg'); import pcot; pcot.setup(); "
            "import pcot.plotting; from pcot.imagecube import ImageCube; "
            "from pcot.utils.histogram import Histogram; "
            "img = ImageCube(np.random.rand(8, 8, 3).astype(np.float32)); "
            "pcot.plotting.histogram(img); Histogram.fromImage(img)._repr_png_(); "
            "print(matplotlib.get_backend(), 'pcot.ui.mplwidget' in sys.modules)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1].lower() == "agg false"
