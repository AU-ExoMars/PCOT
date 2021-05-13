#
# Test basic library functionality
#

import pcot
from pcot.conntypes import IMG

# load a PCOT graph
g = pcot.load("..\\foo.pcot")
# change input 0 to some ENVI data
rv = g.setInputENVI(0, r'..\\RStar_AUPE\AUPE_RWAC_Caltarg_RStar.hdr')
if rv is not None:  # check all is good
    raise Exception(rv)
# then we tell it the graph has changed, and it will run.
g.changed()
# now get an evaluation node by name (which is the same as its expression)
# and read its output 0, which should be an image
img = g.getNodeByName("a*0.5").getOutput(0, IMG)
# get an RGB representation using these wavelengths for RGB
img.setRGBMapping(832, 950, 1000)
# and write to a PNG
img.rgbWrite('output.png')
