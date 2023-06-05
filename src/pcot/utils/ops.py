"""binary and unary operations which work on many kinds of data sensibly."""
from enum import Enum, auto
from typing import Any, Callable, Optional, Dict, Tuple

import numpy as np

from pcot.datum import Datum, Type
from pcot.imagecube import ImageCube
from pcot.number import Number
from pcot.rois import BadOpException, ROI
from pcot.sources import MultiBandSource, SourceSet


class OperatorException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


# Define operator names. Yes, there's a nice functional way of doing this,
# but Pycharm doesn't do completion with that.

class Operator(Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    NEG = auto()
    POW = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    DOLLAR = auto()


# binary operations are stored in a dictionary of (Type,Type,Operator) tuples mapping onto
# functions which take a pair of Datums of the appropriate type and return Datum.
# Opname is the character.

binops: Dict[Tuple[Operator, Type, Type], Callable[[Datum, Datum], Datum]] = {}

# unary operations are stored in a dictionary of key (Type,Operator), mapping onto functions which
# take a Datum and return a Datum

unops: Dict[Tuple[Operator, Type], Callable[[Datum], Datum]] = {}


def registerBinop(op: Operator, lhs: Type, rhs: Type, f: Callable[[Datum, Datum], Datum], forceReplace=False):
    """Register a binary operator function for two types and an operator ID"""
    t = (op, lhs, rhs)
    if t in binops and not forceReplace:
        raise OperatorException(f"trying to re-register binary operation {op.name} for {lhs.name}, {rhs.name}")
    binops[t] = f


def registerUnop(op: Operator, tp: Type, f: Callable[[Datum], Datum], forceReplace=False):
    """Register a unary operator function for a type and an operator ID"""
    t = (op, tp)
    if t in unops and not forceReplace:
        raise OperatorException(f"trying to re-register a unary operation for {tp.name}")
    unops[t] = f


def binop(op: Operator, lhs: Datum, rhs: Datum):
    """Perform a binary operator"""
    try:
        # if either input is None, the output will be None
        if lhs is None or lhs is None:
            return None
        if lhs.isImage() and lhs.isNone() or rhs.isImage() and rhs.isNone():
            raise OperatorException("cannot perform binary operation on None image")

        f = binops[(op, lhs.tp, rhs.tp)]
        return f(lhs, rhs)

    except KeyError:
        raise OperatorException(f"incompatible types for operator {op.name}: {lhs.tp}, {rhs.tp}")


def unop(op: Operator, arg: Datum):
    """Perform a unary operator"""
    try:
        if arg is None:
            return None
        if arg.isImage() and arg.isNone():
            raise OperatorException("cannot perform unary operation on None image")

        f = unops[(op, arg.tp)]
        return f(arg)
    except KeyError:
        raise OperatorException(f"incompatible type for operator {op.name}: {arg.tp}")


def combineImageWithNumberSources(img: ImageCube, other: SourceSet) -> MultiBandSource:
    """This is used to generate the source sets when an image is combined with something else,
    e.g. an image is multiplied by a number. In this case, each band of the image is combined with
    the other sources."""
    x = [x.sourceSet for x in img.sources.sourceSets]

    return MultiBandSource([SourceSet(x.sourceSet.union(other.sourceSet)) for x in img.sources.sourceSets])


def imageUnop(d: Datum, f: Callable[[np.ndarray], np.ndarray]) -> Datum:
    """This wraps unary operations on imagecubes"""
    img = d.val
    if img.hasROI():
        subimg = img.subimage()
        masked = subimg.masked()
        ressubimg = f(masked)
        rimg = img.modifyWithSub(subimg, ressubimg).img
    else:
        rimg = f(img.img)
    out = ImageCube(rimg, sources=img.sources)  # originally this built a new source set. Don't know why.
    out.rois = img.rois.copy()
    return Datum(Datum.IMG, out)


def numberUnop(d: Datum, f: Callable[[Number], Number]) -> Datum:
    """This wraps unary operations on numbers"""
    return Datum(Datum.NUMBER, f(d.val), d.getSources())

# TODO UNCERTAINTY - work out what the args should be and pass them in
def imageBinop(dx: Datum, dy: Datum, f: Callable[[np.ndarray, np.ndarray], ImageCube]) -> Datum:
    """This wraps binary operations on imagecubes"""
    imga = dx.val
    imgb = dy.val

    if imga.img.shape != imgb.img.shape:
        raise OperatorException('Images must be same shape in binary operation')
    # if imga has an ROI, use that for both. Similarly, if imgb has an ROI, use that.
    # But they can't both have ROIs unless they are identical.

    ahasroi = imga.hasROI()
    bhasroi = imgb.hasROI()
    if ahasroi or bhasroi:
        if ahasroi and bhasroi and imga.rois != imgb.rois:
            raise OperatorException('cannot have two images with ROIs on both sides of a binary operation')
        else:
            # get subimages, using their own image's ROI if it has one, otherwise the other image's ROI.
            # One of these will be true.
            rois = imga.rois if ahasroi else imgb.rois
            subimga = imga.subimage(None if ahasroi else imgb)
            subimgb = imgb.subimage(None if bhasroi else imga)

        maskeda = subimga.masked()
        maskedb = subimgb.masked()
        # get masked subimages
        # perform calculation and get result subimage
        ressubimg = f(maskeda, maskedb)  # will generate a numpy array
        # splice that back into a copy of image A, but just take its image, because we're going to
        # rebuild the sources
        img = imga.modifyWithSub(subimga, ressubimg).img
    else:
        # neither image has a roi
        img = f(imga.img, imgb.img)
        rois = None

    sources = MultiBandSource.createBandwiseUnion([imga.sources, imgb.sources])
    outimg = ImageCube(img, sources=sources)
    if rois is not None:
        outimg.rois = rois.copy()
    return Datum(Datum.IMG, outimg)


# TODO UNCERTAINTY - work out what the args should be and pass them in
def numberImageBinop(dx: Datum, dy: Datum, f: Callable[[float, np.ndarray], ImageCube]) -> Datum:
    """This wraps binary operations number x imagecube"""
    num = dx.val.n    # Datum.NUMBER
    img = dy.val    # Datum.IMG
    subimg = img.subimage()
    img = img.modifyWithSub(subimg, f(num, subimg.masked()))
    img.rois = dy.val.rois.copy()
    img.sources = combineImageWithNumberSources(img, dx.getSources())
    return Datum(Datum.IMG, img)


# TODO UNCERTAINTY - work out what the args should be and pass them in
def imageNumberBinop(dx: Datum, dy: Datum, f: Callable[[float, np.ndarray], ImageCube]) -> Datum:
    """This wraps binary operations imagecube x number"""
    img = dx.val    # Datum.IMG
    num = dy.val.n    # Datum.NUMBER

    subimg = img.subimage()
    img = img.modifyWithSub(subimg, f(subimg.masked(), num))  # uncertainty not handled
    img.rois = dx.val.rois.copy()
    img.sources = combineImageWithNumberSources(img, dy.getSources())
    return Datum(Datum.IMG, img)


# TODO UNCERTAINTY - work out what the args should be and pass them in
def numberBinop(dx: Datum, dy: Datum, f: Callable[[Number, Number], Number]) -> Datum:
    """Wraps number x number -> number"""
    r = f(dx.val, dy.val)
    return Datum(Datum.NUMBER, r, SourceSet([dx.getSources(), dy.getSources()]))


def ROIBinop(dx: Datum, dy:Datum, f: Callable[[ROI, ROI], ROI]) -> Datum:
    """wraps ROI x ROI -> ROI"""
    r = f(dx.val, dy.val)
    return Datum(Datum.ROI, r, SourceSet([dx.getSources(), dy.getSources()]))


def extractChannelByName(a: Datum, b: Datum) -> Datum:
    """Extract a channel by name from an image, used for the $ operator.
    a: a Datum which must be an image
    b: a Datum which must be an identifier or numeric wavelength
    return: a new single-channel image datum
    """
    img = a.val

    if b.tp == Datum.NUMBER:
        img = img.getChannelImageByFilter(b.val.n)
    elif b.tp == Datum.IDENT:
        img = img.getChannelImageByFilter(b.val)
    else:
        raise OperatorException("channel extract operator '$' requires ident or numeric wavelength RHS")

    if img is None:
        raise OperatorException("unable to get this wavelength from an image: " + str(b))

    img.rois = a.val.rois.copy()
    return Datum(Datum.IMG, img)

# TODO UNCERTAINTY REWRITE THESE FUNCTIONS
def initOps():
    """Initialise functions. Would be in the top-level, but I get
    some spurious warnings."""

    # should be no need to check for None or Datum.NONE here, that will
    # be done in binop() and unop()

    registerUnop(Operator.NEG, Datum.IMG, lambda datum: imageUnop(datum, lambda x: -x))
    registerUnop(Operator.NOT, Datum.IMG, lambda datum: imageUnop(datum, lambda x: 1 - x))

    registerUnop(Operator.NEG, Datum.NUMBER, lambda datum: numberUnop(datum, lambda x: -x))
    registerUnop(Operator.NOT, Datum.NUMBER, lambda datum: numberUnop(datum, lambda x: ~x))

    def regAllBinops(op, fn):
        """Used to register binops for types which support all operations, including max and min"""
        registerBinop(op, Datum.IMG, Datum.IMG, lambda dx, dy: imageBinop(dx, dy, fn))
        registerBinop(op, Datum.NUMBER, Datum.IMG, lambda dx, dy: numberImageBinop(dx, dy, fn))
        registerBinop(op, Datum.IMG, Datum.NUMBER, lambda dx, dy: imageNumberBinop(dx, dy, fn))
        registerBinop(op, Datum.NUMBER, Datum.NUMBER, lambda dx, dy: numberBinop(dx, dy, fn))

    regAllBinops(Operator.ADD, lambda x, y: x + y)
    regAllBinops(Operator.SUB, lambda x, y: x - y)
    regAllBinops(Operator.MUL, lambda x, y: x * y)
    regAllBinops(Operator.DIV, lambda x, y: x / y)
    regAllBinops(Operator.POW, lambda x, y: x ** y)
    regAllBinops(Operator.AND, lambda x, y: x & y)
    regAllBinops(Operator.OR, lambda x, y: x | y)

    def regROIBinop(op, fn):
        """Used to register binops for ROIs, which support a subset of ops."""
        registerBinop(op, Datum.ROI, Datum.ROI, lambda dx, dy: ROIBinop(dx, dy, fn))

    regROIBinop(Operator.ADD, lambda x, y: x + y)
    regROIBinop(Operator.SUB, lambda x, y: x - y)
    regROIBinop(Operator.MUL, lambda x, y: x * y)
    regROIBinop(Operator.DIV, lambda x, y: x / y)
    regROIBinop(Operator.POW, lambda x, y: x ** y)

    registerBinop(Operator.DOLLAR, Datum.IMG, Datum.NUMBER, extractChannelByName)
    registerBinop(Operator.DOLLAR, Datum.IMG, Datum.IDENT, extractChannelByName)


initOps()
