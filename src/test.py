#
# Test basic library functionality
#
import os

import pcot

print("OK")

try:
    # read the graph - but it's the wrong directory!
    g = pcot.load("..\\foo.pcot")
    # you see, input 0 can't read its file (and the above will fail) so we're going to get the active input method
    # for input 0 (which we know is ENVI) and change its filename.
    g.inputMgr.inputs[0].getActive().fname = '..\\RStar_AUPE\AUPE_RWAC_Caltarg_RStar.hdr'
    # then we tell it the graph has changed, and it will rerun successfully.
    g.changed()
except FileNotFoundError as e:
    print("oops: "+str(e))
