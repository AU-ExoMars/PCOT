"""
This package deals with ancillary data attached to ImageCube objects. This is read either from the data
itself (ENVI, PDS4) or from files of similar names parallel to the image data (multifile).

Ancillary data is typically per-band, although we may need to support either data for the cube a whole.

A typical example of ancillary data is the exposure time of a particular band.

The data is read in this package, but reading is invoked by the InputMethod. Reading needs to be very
flexible - both in determining the data source (e.g. the name of the parallel .xml file to a .png fiile)
and in processing it (because different cameras and versions of their export software may produce different
XML files).
"""

from pcot.ancillary.multifile import multifile_loader

# importing the built-in loaders registers them
import pcot.ancillary.aupe

