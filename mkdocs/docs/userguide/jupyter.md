# Using PCOT in Jupyter notebooks

PCOT can be used from [Jupyter](https://jupyter.org/) notebooks (JupyterLab or the classic
notebook) to load and process data, look at images and spectra, and pass results on to other
Python tools such as pandas. You can run PCOT documents made in the application, or use PCOT's
functions directly.

This page covers what's specific to notebooks. For more on using PCOT from Python - building
documents in code, using PCOT's functions without a document - see
[Using PCOT as a library](../devguide/library.md).

## Installing

PCOT and Jupyter need to be installed in the same Python environment. The simplest way is to
install both with pip, into a new environment using Python 3.11 or 3.12:

```shell
conda create -n pcotnb python=3.12
conda activate pcotnb
pip install pcot jupyterlab
jupyter lab
```

PCOT doesn't come with camera or reflectance data - see
[Installing with pip](../gettingstarted/installrun.md#installing-with-pip) for how to get them.

If you have installed PCOT from the repository with Poetry (for example, to work on the latest
development version), you can add Jupyter to that environment with `pip install jupyterlab`.
Poetry doesn't know about packages installed this way, so a later `poetry install` may change
packages Jupyter depends on; keeping a separate environment for notebooks avoids this.

## Starting PCOT

PCOT must be set up once in each notebook, before anything else is done with it:

```python
import pcot
pcot.setup()
```

This loads plugins, camera and reflectance data, and PCOT's settings (the same settings the
PCOT application uses).

## Getting data

### From a PCOT document

A document made in the PCOT application can be loaded and run. Nodes can then be found by
name, and their outputs read:

```python
from pcot.document import Document
from pcot.datum import Datum

doc = Document("example.pcot")
doc.run()

img = doc.getNodeByName("multidot").getOutputDatum(0).get(Datum.IMG)
spectra = doc.getNodeByName("spectrum").getOutputDatum(0)
```

`getNodeByName` raises an error if there is no node with that name, or more than one. A *sink*
node has no outputs: what it receives is in its `data` field instead, e.g.
`doc.getNodeByName("sink").data`.

### Loading files directly

Image files can also be loaded without a document, using the functions in
`pcot.dataformats.load` - for example `load.envi(...)` for ENVI files, `load.multifile(...)` for
sets of single-band images, and `load.pds4(...)` for PDS4 products. Each returns a `Datum`
holding the image. See [Using PCOT as a library](../devguide/library.md#using-pcot-functions-and-data-types-without-a-graph)
for an example.

## Looking at images

Images display themselves: if an image (or a `Datum` holding one) is the value of a cell, the
notebook shows it as an annotated export would look - using the image's RGB channel mapping, with
its regions of interest and annotations. Small images are scaled up so their annotations can be
read.

```python
img
```

The pixel data is available as numpy arrays: `img.img` holds the values (height × width ×
bands), `img.uncertainty` their uncertainties, and `img.dq` the data quality bits. `img.rgb()`
gives just the three bands of the RGB mapping, which can be shown with matplotlib's `imshow` -
but note that the values are not normalised as PCOT's canvas normalises them, so values above 1
need clipping or scaling first.

## Plotting spectra

Sets of spectra display themselves too, as a spectrum plot with the *spectrum* node's default
settings:

```python
spectra
```

For other settings, or to draw into your own figure, use `pcot.plotting.spectrum`. It takes any
of the spectrum node's plot settings as keyword arguments:

```python
import pcot.plotting

pcot.plotting.spectrum(spectra, errorbarmode="stderror", stackSep=5, wavelength_units="microns")
```

`pcot.plotting.spectrumSettings()` lists the settings and their defaults. To draw a spectrum
node's plot exactly as the node shows it, with the node's own settings and order, use
`pcot.plotting.spectrumFromNode(node)`.

These functions draw onto a new matplotlib figure, or onto axes you pass as the second argument,
and return the axes - so they can be combined with other plots:

```python
import matplotlib.pyplot as plt

fig, (left, right) = plt.subplots(1, 2, figsize=(10, 3))
pcot.plotting.spectrum(spectra, left, annotate="line")
pcot.plotting.spectrum(otherSpectra, right)
```

The notebook also prints the returned axes; end the line with `;` to hide that. For interactive
plots that can be zoomed and panned, install the `ipympl` package and run `%matplotlib widget`
in the notebook.

## Tables

Data which PCOT can show as a table - such as spectra and tables - can be turned into a pandas
DataFrame (install pandas with `pip install pandas` if you don't have it):

```python
import io
import pandas as pd

pd.read_csv(io.StringIO(spectra.getTabularProvider().csvString()))
```

## Messages

PCOT only shows its warnings and errors in notebooks. To see its informational messages as
well, see [Logging](../devguide/library.md#logging).

## Running on a server

PCOT uses Qt, which normally needs a display, even though notebooks don't show any PCOT windows.
If PCOT fails to start on a machine with no display (such as a remote Jupyter server), try setting
the environment variable `QT_QPA_PLATFORM=offscreen` before starting Jupyter.
