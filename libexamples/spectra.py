"""
Load an image, place two circular ROIs, generate HTML tables
showing the spectra at those ROIs
"""

from pcot.datum import Datum
from pcot.rois import ROICircle
from pcot.utils.spectrum import SpectrumSet
from pcot.dataformats import load

# load an image
datum = load.envi("/media/xfer/PCOTdata/RStar_AUPE/AUPE_LWAC_Caltarg_RStar.hdr")

# get the image from the datum
img = datum.get(Datum.IMG)

# add a couple of circular ROIs to the image
img.rois.append(ROICircle(50, 40, 4, label="a"))
img.rois.append(ROICircle(8, 8, 4, label="b"))

# generate a spectrum set and convert the results to a table
ss = SpectrumSet({"in": img}).table().html()
# print
print(ss)
