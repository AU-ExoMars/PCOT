# This is the application-specific part of the expression parsing system.
# In this system, all data is a Datum object.
import math
import numbers
from typing import Callable, Dict, Tuple, List, Optional, Any

import numpy as np
import cv2 as cv
import pcot.conntypes as conntypes
import pcot.operations as operations
from pcot.expressions import parse
from pcot.expressions.parse import Stack
from pcot.pancamimage import ImageCube
from pcot.utils.ops import binop, unop
from pcot.xform import Datum, XFormException


# TODO: Show output in canvas (and other output somehow if not image?). Honour the ROI from the "leftmost" image with an ROI - So A has priority over B, etc.
# TODO: keep expression guide in help updated


class InstNumber(parse.Instruction):
    """constant number instruction"""
    val: float

    def __init__(self, v: float):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(conntypes.NUMBER, self.val))

    def __str__(self):
        return "NUM {}".format(self.val)


class InstIdent(parse.Instruction):
    """constant string identifier instruction"""
    val: str

    def __init__(self, v: str):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(conntypes.IDENT, self.val))

    def __str__(self):
        return "IDENT {}".format(self.val)


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


def funcMerge(args):
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
        else:
            bands = bands + cv.split(x.img)
        sources = sources + x.sources

    img = np.stack(bands, axis=-1)
    img = ImageCube(img, None, sources)

    return Datum(conntypes.IMG, img)


def chkargs(fname, args: List[Optional[Datum]], types: List[conntypes.Type], optTypes: List[Tuple[conntypes.Type, Any]]):
    """Process arguments, returning a pair of lists of Datum items: mandatory and optional args.
    Takes two lists: one of types of mandatory values (none of which can be None) and another of pairs of
    type, defaultvalue for optional args"""
    mandatArgs = []
    optArgs = []
    for t in types:
        if len(args) == 0:
            raise XFormException('EXPR', 'Out of arguments in {}'.format(fname))
        x = args.pop(0)
        if x is None:
            raise XFormException('EXPR', 'None argument in {}'.format(fname))
        elif x.tp != t:
            raise XFormException('EXPR', 'Bad argument in {}, got {}, expected {}'.format(fname, x.tp, t))
        mandatArgs.append(x)

    for t, deflt in optTypes:
        if len(args) == 0:
            optArgs.append(deflt)
        else:
            x = args.pop(0)
            if x is None:
                raise XFormException('EXPR', 'None argument in {}'.format(fname))
            elif x.tp != t:
                raise XFormException('EXPR', 'Bad argument in {}, got {}, expected {}'.format(fname, x.tp, t))
            optArgs.append(x)

    return mandatArgs, optArgs


def funcGrey(args):
    """Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean."""

    # args : Image, use cv conversion [default false]
    args, optargs = chkargs('grey', args, [conntypes.IMG], [(conntypes.NUMBER, 0)])

    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for merge')

    img = args[0].get(conntypes.IMG)
    sources = set.union(*img.sources)

    if optargs[0] != 0:
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
            raise XFormException('EXPR', 'internal: fn returns bad type')
    elif d.tp == conntypes.NUMBER:  # deal with numeric argument (always returns a numeric result)
        return Datum(conntypes.NUMBER, fn(d.val))


class ExpressionEvaluator(parse.Parser):
    """The core class for the expression evaluator, based on a generic Parser."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__(True)  # naked identifiers permitted
        self.registerNumInstFactory(lambda x: InstNumber(x))  # make sure we stack numbers as Datums
        self.registerIdentInstFactory(lambda x: InstIdent(x))  # identifiers too
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

        self.registerFunc("merge", funcMerge)
        self.registerFunc("sin", lambda args: funcWrapper(np.sin, args[0]))
        self.registerFunc("cos", lambda args: funcWrapper(np.cos, args[0]))
        self.registerFunc("tan", lambda args: funcWrapper(np.tan, args[0]))
        self.registerFunc("sqrt", lambda args: funcWrapper(np.sqrt, args[0]))

        self.registerFunc("min", lambda args: funcWrapper(np.min, args[0]))
        self.registerFunc("max", lambda args: funcWrapper(np.max, args[0]))
        self.registerFunc("sd", lambda args: funcWrapper(np.std, args[0]))
        self.registerFunc("mean", lambda args: funcWrapper(np.mean, args[0]))

        self.registerFunc("grey", funcGrey)

        registerProperty('w', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.w))
        registerProperty('h', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.h))

    def run(self, s):
        """Parse and evaluate an expression."""
        self.parse(s)

        stack = []
        return parse.execute(self.output, stack)
