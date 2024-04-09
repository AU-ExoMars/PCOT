"""
Load an ENVI file. Then, for each band, save files with names of the
form imgXXX.png where XXX is the wavelength of the band. Each file
is a colourised representation of the band, where the colour is an RGB
approximation of the filter colour. Used primarily for outreach.
"""



import numpy as np

from pcot import dq
from pcot.datum import Datum
from pcot.value import Value
import pcot.datumfuncs as df
from pcot.dataformats import load
from pcot.filters import wav2RGB
from pcot.datumfuncs import merge

d = load.envi("/media/xfer/PCOTdata/RStar_AUPE/AUPE_LWAC_Caltarg_RStar.hdr")

img = d.get(Datum.IMG)

for chan in range(img.channels):
    w = img.wavelength(chan)
    r, g, b = wav2RGB(w)
    
    # get a single image of that channel
    mono = d % Datum.k(w)
    
    x = merge(mono*Datum.k(r),mono*Datum.k(g),mono*Datum.k(b))
              
    Datum.get(x,Datum.IMG).rgbWrite(f"img{int(w)}.png")
    
