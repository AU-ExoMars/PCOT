#
# Test basic library functionality
#
import os

import pcot

print("OK")

try:
    # read the graph - but it's the wrong directory!
    g = pcot.load("..\\foo.pcot")
    g.inputMgr.inputs[0].setActiveMethod(pcot.inputs.Input.ENVI)
    g.inputMgr.inputs[0].getActive().setFileName(r'..\\RStar_AUPE\AUPE_RWAC_Caltarg_RStar.hdr')
    # then we tell it the graph has changed, and it will run.
    g.changed()
except FileNotFoundError as e:
    print("oops: " + str(e))
