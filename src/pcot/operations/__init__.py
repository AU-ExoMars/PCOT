## This package manages "operation functions" : these are functions which take a subimage (i.e. bounding box around an
# ROI and mask data) and some other optional data, and return an ImageCube. They can be used three ways:
# as an XForm node, as a function in an eval node, and as a plain Python function.
from typing import Callable, Dict, Any

import numpy as np

import pcot.operations.norm
import pcot.operations.curve
from pcot.expressions import Parameter
from pcot.pancamimage import SubImageCubeROI
from pcot.xform import XForm
from pcot.datum import Datum


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
    img = node.getInput(0, Datum.IMG)
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
    node.setOutput(0, Datum(Datum.IMG, node.img))


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
# back into the image. It's a little different from the funcWrapper in eval.py, which can take images and numbers.

def exprWrapper(fn, img, *args):
    if img is None:
        return None
    subimage = img.subimage()
    newsubimg = fn(subimage, *args)
    img = img.modifyWithSub(subimage, newsubimg)
    return Datum(Datum.IMG, img)


## Register additional functions and properties into a Parser.


def registerOpFunctionsAndProperties(p: 'Parser'):
    p.registerFunc(
        "curve",
        "impose a sigmoid curve on an image, y=1/(1+e^-(mx+a))) where m and a are parameters",
        [Parameter("image", "the image to process", Datum.IMG),
         Parameter("mul", "multiply pixel values by this factor before processing", Datum.NUMBER),
         Parameter("add", "add this to pixels values after multiplication", Datum.NUMBER)],
        [],
        lambda args, optargs: exprWrapper(curve.curve, *getData(args, Datum.IMG, Datum.NUMBER, Datum.NUMBER))
    )

    p.registerFunc(
        "norm",
        "normalize all channels of an image to 0-1, operating on all channels combined (the default) or separately",
        [Parameter("image", "the image to process", Datum.IMG)],
        [Parameter("splitchans", "if nonzero, process each channel separately", Datum.NUMBER, deflt=0)],
        lambda args, optargs: exprWrapper(norm.norm, getDatum(args[0], Datum.IMG), 0, getDatum(optargs[0], Datum.NUMBER))
    )

    p.registerFunc(
        "clip",
        "clip  all channels of an image to 0-1",
        [Parameter("image", "the image to process", Datum.IMG)],
        [],
        lambda args, optargs: exprWrapper(norm.norm, getDatum(args[0], Datum.IMG), 1))
