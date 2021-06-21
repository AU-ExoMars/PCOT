# This is the application-specific part of the expression parsing system.
# In this system, all data is a Datum object.
import math
import numbers
from typing import Callable, Dict, Tuple, List, Optional, Any

import numpy as np
import cv2 as cv

import pcot.config
import pcot.conntypes as conntypes
import pcot.operations as operations
from pcot.expressions import parse
from pcot.expressions.parse import Parameter
from pcot.pancamimage import ImageCube
from pcot.utils.ops import binop, unop
from pcot.xform import XFormException
from pcot.conntypes import Datum


# TODO: Show output in canvas (and other output somehow if not image?). Honour the ROI from the "leftmost" image with an ROI - So A has priority over B, etc.
# TODO: keep expression guide in help updated


def extractChannelByName(a: Datum, b: Datum):
    if a is None or b is None:
        return None

    if a.tp != conntypes.IMG:
        raise XFormException('DATA', "channel extract operator '$' requires image LHS")
    img = a.val

    if b.tp == conntypes.NUMBER:
        img = img.getChannelImageByWavelength(b.val)
    elif b.tp == conntypes.IDENT:
        img = img.getChannelImageByName(b.val)
    else:
        raise XFormException('DATA', "channel extract operator '$' requires ident or numeric wavelength RHS")

    if img is None:
        raise XFormException('EXPR', "unable to get this wavelength from an image: " + str(b))

    img.rois = a.val.rois.copy()
    return Datum(conntypes.IMG, img)


# property dict - keys are (name,type).

properties: Dict[Tuple[str, conntypes.Type], Callable[[Datum], Datum]] = {}


def registerProperty(name: str, tp: conntypes.Type, func: Callable[[Datum], Datum]):
    """add a property (e.g. the 'w' in 'a.w'), given name, input type and function"""
    properties[(name, tp)] = func


def getProperty(a: Datum, b: Datum):
    if a is None:
        raise XFormException('EXPR', 'first argument is None in "." operator')
    if b is None:
        raise XFormException('EXPR', 'second argument is None in "." operator')
    if b.tp != conntypes.IDENT:
        raise XFormException('EXPR', 'second argument should be identifier in "." operator')
    propName = b.val

    try:
        func = properties[(propName, a.tp)]
        return func(a)
    except KeyError:
        raise XFormException('EXPR', 'unknown property "{}" for given type in "." operator'.format(propName))


def funcMerge(args, optargs):
    """function for merging a number of images"""
    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for merge')
    if any([not x.isImage() for x in args]):
        raise XFormException('EXPR', 'merge only accepts images')

    args = [x.get(conntypes.IMG) for x in args]

    bands = []
    sources = []
    for x in args:
        if x.channels == 1:
            bands.append(x.img)
            print(x.img)
        else:
            bands = bands + cv.split(x.img)
        sources = sources + x.sources

    img = np.stack(bands, axis=-1)
    img = ImageCube(img, None, sources)

    return Datum(conntypes.IMG, img)


def funcGrey(args, optargs):
    """Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean."""

    img = args[0].get(conntypes.IMG)
    sources = set.union(*img.sources)

    if optargs[0].get(conntypes.NUMBER) != 0:
        if img.channels != 3:
            raise XFormException('DATA', "Image must be RGB for OpenCV greyscale conversion")
        img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY), img.mapping, [sources])
    else:
        # create a transformation matrix specifying that the output is a single channel which
        # is the mean of all the channels in the source
        mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
        out = cv.transform(img.img, mat)
        img = ImageCube(out, img.mapping, [sources])
    return Datum(conntypes.IMG, img)


def funcWrapper(fn, d, *args):
    """Wrapper around a evaluator function that deals with ROIs etc.
    compare this with exprWrapper in operations, which only handles images and delegates
    processing ROI stuff to the function."""
    if d is None:
        return None
    elif d.isImage():  # deal with image argument
        img = d.val
        subimage = img.subimage()
        mask = subimage.fullmask()
        cp = subimage.img.copy()
        masked = np.ma.masked_array(cp, mask=~mask)
        newdata = fn(masked, *args)  # the result of this could be *anything*
        # so now we look at the result and build an appropriate Datum
        if isinstance(newdata, np.ndarray):
            np.putmask(cp, mask, newdata)
            img = img.modifyWithSub(subimage, newdata)
            return Datum(conntypes.IMG, img)
        elif isinstance(newdata, numbers.Number):
            return Datum(conntypes.NUMBER, float(newdata))
        else:
            raise XFormException('EXPR', 'internal: fn returns bad type in funcWrapper')
    elif d.tp == conntypes.NUMBER:  # deal with numeric argument (always returns a numeric result)
        return Datum(conntypes.NUMBER, fn(d.val, *args))


def statsWrapper(fn, d: List[Optional[Datum]], *args):
    """similar to funcWrapper, but can take lots of image and number arguments which it aggregates to do stats on.
    The result of fn must be a number. Works by flattening any images and concatenating them with any numbers,
    and doing the operation on the resulting data."""
    intermediate = None
    for x in d:
        if x is None:
            continue
        elif x.isImage():
            subimage = x.val.subimage()
            mask = subimage.fullmask()
            cp = subimage.img.copy()
            masked = np.ma.masked_array(cp, mask=~mask)
            # we convert the data into a flat numpy array if it isn't one already
            if isinstance(masked, np.ma.masked_array):
                newdata = masked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(masked, np.ndarray):
                newdata = masked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: fn returns bad type in statsWrapper')
        elif x.tp == conntypes.NUMBER:
            newdata = np.array([x.val], np.float32)
        else:
            raise XFormException('EXPR', 'internal: bad type passed to statsWrapper')

        # and add it to the intermediate array
        if intermediate is None:
            intermediate = newdata
        else:
            intermediate = np.concatenate((intermediate, newdata))

    # then we perform the function on the collated array
    return Datum(conntypes.NUMBER, fn(intermediate, *args))


class ExpressionEvaluator(parse.Parser):
    """The core class for the expression evaluator, based on a generic Parser. The constructor
    is responsible for registering most functions."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__(True)  # naked identifiers permitted
        self.registerBinop('+', 10, lambda a, b: binop(a, b, lambda x, y: x + y, None))
        self.registerBinop('-', 10, lambda a, b: binop(a, b, lambda x, y: x - y, None))
        self.registerBinop('/', 20, lambda a, b: binop(a, b, lambda x, y: x / y, None))
        self.registerBinop('*', 20, lambda a, b: binop(a, b, lambda x, y: x * y, None))
        self.registerBinop('^', 30, lambda a, b: binop(a, b, lambda x, y: x ** y, None))

        self.registerUnop('-', 50, lambda x: unop(x, lambda a: -a, None))

        self.registerBinop('.', 80, getProperty)
        self.registerBinop('$', 100, extractChannelByName)

        # additional functions and properties - this is in the __init__.py in the operations package.
        operations.registerOpFunctionsAndProperties(self)

        self.registerFunc("merge", "merge a number of images into a single image - if the image has multiple channels they will all be merged in.",
                          [Parameter("image", "an image of any depth", conntypes.IMG)],
                          [],
                          funcMerge, varargs=True)
        self.registerFunc("sin", "calculate sine of angle in radians",
                          [Parameter("angle", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.sin, args[0]))
        self.registerFunc("cos", "calculate cosine of angle in radians",
                          [Parameter("angle", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.cos, args[0]))
        self.registerFunc("tan", "calculate tangent of angle in radians",
                          [Parameter("angle", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.tan, args[0]))
        self.registerFunc("sqrt", "calculate the square root",
                          [Parameter("angle", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.sqrt, args[0]))

        self.registerFunc("min", "find the minimum value of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.min, args), varargs=True)
        self.registerFunc("max", "find the maximum value of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.max, args), varargs=True)
        self.registerFunc("sd", "find the standard deviation of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.std, args), varargs=True)
        self.registerFunc("mean", "find the standard deviation of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (conntypes.NUMBER, conntypes.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.mean, args), varargs=True)

        self.registerFunc("grey", "convert an image to greyscale",
                          [Parameter("image", "an image to process", conntypes.IMG)],
                          [Parameter("useCV",
                                     "if non-zero, use openCV greyscale conversion (RGB input only): 0.299*R + 0.587*G + 0.114*B",
                                     conntypes.NUMBER, deflt=0)],
                          funcGrey)

        for x in pcot.config.exprFuncHooks:
            x(self)

        registerProperty('w', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.w))
        registerProperty('h', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.h))
        registerProperty('n', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.h * x.val.w))

    def run(self, s):
        """Parse and evaluate an expression."""
        self.parse(s)

        stack = []
        return parse.execute(self.output, stack)
