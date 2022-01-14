#
# Test basic library functionality
#

from pcot.document import Document
from pcot.datum import Datum

# load a PCOT document
d = Document("..\\libtest.pcot")
# change input 0 to some ENVI data
rv = d.setInputENVI(0, r'..\\RStar_AUPE\AUPE_RWAC_Caltarg_RStar.hdr')
if rv is not None:  # check all is good
    raise Exception(rv)
# then we tell it the graph has changed, and it will run.
d.changed()
# now get an evaluation node by name (which is the same as its expression)
# and read its output 0, which should be an image
img = d.getNodeByName("a*0.5").getOutput(0, Datum.IMG)
# get an RGB representation using these wavelengths for RGB
img.setRGBMapping(832, 950, 1000)
# and write to a PNG
img.rgbWrite('output.png')
