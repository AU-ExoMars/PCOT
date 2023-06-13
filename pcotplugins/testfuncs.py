import cv2 as cv
import numpy as np

from pcot.sources import SourceSet
from pcot.xform import XFormType, xformtype
from pcot.xforms.tabdata import TabData
from pcot.imagecube import ImageCube
from pcot.datum import Datum, Type
from pcot.utils.ops import combineImageWithNumberSources
from PySide2.QtGui import QColor

import pcot.config


# The first part of the plugin creates a new type of node.

# this decorator will cause the node to auto-register.

def dqset(args, optargs):
    inimg = args[0].get(Datum.IMG)  # get the first argument, which is numeric
    bits = args[1].get(Datum.NUMBER)  # and the second argument.

    s = inimg.subimage()
    img = inimg.modifyWithSub(s, None, dqOR=int(bits.n))

    img.rois = inimg.rois.copy()
    img.sources = combineImageWithNumberSources(inimg, args[1].getSources())
    return Datum(Datum.IMG, img)


# Now we have our two function definitions and associated things we can register them.

def regfuncs(p):
    # late import of Parameter to avoid cyclic import problems.
    from pcot.expressions import Parameter
    # register our function.
    p.registerFunc("dqset",  # name
                   "sets DQ bits",  # description
                   # a list defining our parameters by name, description and type
                   [Parameter("a", "image", Datum.IMG),
                    Parameter("b", "bits (as a mask)", Datum.NUMBER)
                    ],
                   # the empty list of optional parameters
                   [],
                   # the function reference
                   dqset)


# this will add a hook to the system to register these functions when the expression parser
# is created (which has to be done quite late).
pcot.config.addExprFuncHook(regfuncs)
