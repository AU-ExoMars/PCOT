## This package manages "operation functions" : these are functions which take a subimage (i.e. bounding box around an
# ROI and mask data) and some other optional data, and return an ImageCube. They can be used three ways:
# as an XForm node, as a function in an eval node, and as a plain Python function.
import inspect
from typing import Tuple, Callable, Dict, Any

import numpy as np

from pcot.conntypes import NUMBER, IMG
import pcot.operations.norm
import pcot.operations.curve
from pcot.expressions.eval import registerProperty
from pcot.pancamimage import ImageCube, SubImageCubeROI
from pcot.xform import Datum, XForm, XFormException


## This is the function which allows XForm nodes to use operation functions.
## takes an image and performs a function on it; use from the perform method of an XForm.
# The image is assumed to be input 0 of the node.
# The function takes the subimage, and should only perform the operation on the subimage.
# It also passes the kwargs into the function - this is how extra parameters get in.
# Other assumptions - node.img and node.mapping are used to output and RGBmap the image,
# image is output on connection 0.
# See norm.py, xformnorm.py for example.

def performOp(node: XForm, fn: Callable[[SubImageCubeROI, XForm, Dict[str, Any]], np.ndarray], **kwargs):
    # get input 0 (the image)
    img = node.getInput(0, IMG)
    # if it's None then the input isn't connected; just output None
    if img is None:
        node.img = None
    elif not node.enabled:
        # if the node isn't enabled,  just output the input image
        node.img = img
    else:
        # otherwise the SubImageCubeROI object from the image - this is the image clipped to
        # a BB around the ROI, with a mask for which pixels are in the ROI.
        subimage = img.copy().subimage()  # make a copy (need to do this to avoid overwriting the source).

        # perform our function, returning a numpy array which
        # is a modified clipped image. We also pass the kwargs, expanding them first - optional
        # data goes here (e.g. norm() has a "mode" setting).
        newsubimg = fn(subimage, **kwargs)

        # splice the returned clipped image into the main image, producing a new image, and
        # store it in the node
        node.img = img.modifyWithSub(subimage, newsubimg)

    if node.img is not None:
        # if there's an image stored in the node, set the image's RGB mapping to be the node's
        # primary mapping (the default one)
        node.img.setMapping(node.mapping)

    # output the current value of node.img
    node.setOutput(0, Datum(IMG, node.img))


## used to register op functions as lambdas - takes a datum and type and returns either None (if it's none or
# the wrong type) or the value.

def getDatum(datum, tp):
    return None if datum is None else datum.get(tp)


## used to register op functions as lambdas - takes an argument list (Datums) for a function
# and the remaining arguments a list of types. Returns a list containing for each Datum either None
# or the contained data.

def getData(args, *argTypes):
    return [getDatum(datum, tp) for datum, tp in zip(args, argTypes)]


## used to register op functions as lambdas - takes a function, an image, and remaining args. Performs the
# necessary magic to extract ROI bounded image, perform the function on that subimage, and plug the subimage
# back into the image.

def exprWrapper(fn, img, *args):
    if img is None:
        return None
    subimage = img.subimage()
    newsubimg = fn(subimage, *args)
    img = img.modifyWithSub(subimage, newsubimg)
    return Datum(IMG, img)


## Register additional functions and properties into a Parser.


def registerOpFunctionsAndProperties(p: 'Parser'):
    p.registerFunc("curve", lambda args: exprWrapper(curve.curve, *getData(args, IMG, NUMBER, NUMBER)))
#    p.registerFunc("norm", lambda args: exprWrapper(norm.norm, getDatum(args[0], IMG), 0))
#    p.registerFunc("clip", lambda args: exprWrapper(norm.norm, getDatum(args[0], IMG), 1))

    registerProperty("norm", IMG, lambda x: exprWrapper(norm.norm, getDatum(x, IMG), 0))
    registerProperty("clip", IMG, lambda x: exprWrapper(norm.norm, getDatum(x, IMG), 1))
