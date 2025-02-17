"""binary and unary operations which work on many kinds of data sensibly."""
from enum import Enum, auto
from typing import Any, Callable, Optional, Dict, Tuple, Union

import numpy as np

from pcot.datum import Datum

from pcot.datumtypes import Type
from pcot.imagecube import ImageCube
from pcot.rois import BadOpException, ROI
from pcot.sources import MultiBandSource, SourceSet, nullSourceSet, SourcesObtainable
from pcot.value import Value


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


def registerBinopSemantics(op: Operator, lhs: Type, rhs: Type, f: Callable[[Datum, Datum], Datum], forceReplace=False):
    """Register a binary operator function for two types and an operator ID"""
    t = (op, lhs, rhs)
    if t in binops and not forceReplace:
        raise OperatorException(f"trying to re-register binary operation {op.name} for {lhs.name}, {rhs.name}")
    binops[t] = f


def registerUnopSemantics(op: Operator, tp: Type, f: Callable[[Datum], Datum], forceReplace=False):
    """Register a unary operator function for a type and an operator ID"""
    t = (op, tp)
    if t in unops and not forceReplace:
        raise OperatorException(f"trying to re-register a unary operation for {tp.name}")
    unops[t] = f


def binop(op: Operator, lhs: Union[Datum,float], rhs: Union[Datum,float]):
    """Perform a binary operator"""
    from numbers import Number
    try:
        if isinstance(lhs, Number):
            lhs = Datum(Datum.NUMBER, Value(lhs, 0), nullSourceSet)
        if isinstance(rhs, Number):
            rhs = Datum(Datum.NUMBER, Value(rhs, 0), nullSourceSet)
        if isinstance(rhs, str):        # used when we do band extraction
            rhs = Datum(Datum.IDENT, rhs, nullSourceSet)

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

    return MultiBandSource([SourceSet(x.sourceSet.union(other.sourceSet)) for x in img.sources.sourceSets])


#
#  These are the "binop semantics Datum wrappers" - they take Datum objects of various types,
#  convert to Values (or extract Values), perform Value operations on them, and return a new Datum.
#  Generally, anyway. imageUnop actually extracts ndarray and performs operations on that, making
#  the assumption that unops have no effect on uncertainty or DQ.

def imageUnop(d: Datum, f: Callable[[np.ndarray], np.ndarray]) -> Datum:
    """This wraps unary operations on imagecubes

    NOTE THAT this assumes that all unops have NO EFFECT on DQ or uncertainty."""
    img = d.val
    if img.hasROI():
        subimg = img.subimage()
        masked = subimg.masked()
        ressubimg = f(masked)
        rimg = img.modifyWithSub(subimg, ressubimg).img
    else:
        rimg = f(img.img)

    # originally this built a new source set. Don't know why. We do, however, copy the uncertainty
    # and DQ from the original image.
    out = ImageCube(rimg, sources=img.sources, uncertainty=np.copy(img.uncertainty), dq=np.copy(img.dq))
    out.rois = img.rois.copy()
    return Datum(Datum.IMG, out)


def numberUnop(d: Datum, f: Callable[[Value], Value]) -> Datum:
    """This wraps unary operations on numbers"""
    return Datum(Datum.NUMBER, f(d.val), d.getSources())


def combineSources(a: SourcesObtainable, b: SourcesObtainable) -> SourcesObtainable:
    if isinstance(a, MultiBandSource) and isinstance(b, MultiBandSource):
        # if both sources are multiband, do a bandwise union
        return MultiBandSource.createBandwiseUnion([a, b])
    elif isinstance(a, MultiBandSource) and not isinstance(b, MultiBandSource):
        # if one source is multiband, add the other to each band
        return MultiBandSource([SourceSet(x.sourceSet.union(b.getSources())) for x in a.sourceSets])
    elif not isinstance(a, MultiBandSource) and isinstance(b, MultiBandSource):
        # same again but other way round
        return MultiBandSource([SourceSet(x.sourceSet.union(a.getSources())) for x in b.sourceSets])
    else:
        # neither is multiband, just union them
        return SourceSet(a.getSources().sourceSet.union(b.getSources().sourceSet))


def imageBinop(dx: Datum, dy: Datum, f: Callable[[Value, Value], Value]) -> Datum:
    """This wraps binary operations on imagecubes"""
    imga = dx.val
    imgb = dy.val

    if imga.img.shape != imgb.img.shape:
        raise OperatorException('Images must be same shape in binary operation')

    # if imga has an ROI, use that for both. Similarly, if imgb has an ROI, use that.
    # But they can't both have ROIs unless they are identical.

    ahasroi = imga.hasROI()
    bhasroi = imgb.hasROI()
    if ahasroi and bhasroi and imga.rois != imgb.rois:
        raise OperatorException('cannot have two images with ROIs on both sides of a binary operation')

    # we make a subimage even if there is no ROI - it's just easier to manage.

    rois = imga.rois if ahasroi else imgb.rois
    subimga = imga.subimage(None if ahasroi else imgb)
    subimgb = imgb.subimage(None if bhasroi else imga)

    a = Value(subimga.masked(), subimga.maskedUncertainty(), subimga.maskedDQ())
    b = Value(subimgb.masked(), subimgb.maskedUncertainty(), subimgb.maskedDQ())
    # perform calculation and get result subimage
    r = f(a, b)  # will generate a value
    # splice that back into a copy of image A replacing uncertainty and DQ too.
    outimg = imga.modifyWithSub(subimga, r.n, uncertainty=r.u, dqv=r.dq)

    outimg.sources = MultiBandSource.createBandwiseUnion([imga.sources, imgb.sources])
    if rois is not None:
        outimg.rois = rois.copy()

    return Datum(Datum.IMG, outimg)


def numberImageBinop(dx: Datum, dy: Datum, f: Callable[[Value, Value], Value]) -> Datum:
    """This wraps binary operations number x imagecube"""
    # get the image
    img = dy.val
    # create a subimage
    subimg = img.subimage()
    # get the uncertainty-aware forms of the operands
    b = Value(subimg.masked(), subimg.maskedUncertainty(), subimg.maskedDQ())
    # perform the operation
    r = f(dx.val, b)
    # put the result back into the image
    img = img.modifyWithSub(subimg, r.n, uncertainty=r.u, dqv=r.dq)
    # handle ROIs and sources
    img.rois = dy.val.rois.copy()
    img.sources = combineSources(img.sources, dx.sources)
    return Datum(Datum.IMG, img)


def imageNumberBinop(dx: Datum, dy: Datum, f: Callable[[Value, Value], Value]) -> Datum:
    """This wraps binary operations imagecube x number"""
    img = dx.val  # Datum.IMG
    subimg = img.subimage()
    a = Value(subimg.masked(), subimg.maskedUncertainty(), subimg.maskedDQ())
    r = f(a, dy.val)
    img = img.modifyWithSub(subimg, r.n, uncertainty=r.u, dqv=r.dq)
    img.rois = dx.val.rois.copy()
    img.sources = combineSources(img.sources, dy.sources)
    return Datum(Datum.IMG, img)


def numberBinop(dx: Datum, dy: Datum, f: Callable[[Value, Value], Value]) -> Datum:
    """Wraps number x number -> number"""
    r = f(dx.val, dy.val)
    sources = combineSources(dx.sources, dy.sources)
    return Datum(Datum.NUMBER, r, sources)


def ROIBinop(dx: Datum, dy: Datum, f: Callable[[ROI, ROI], ROI]) -> Datum:
    """wraps ROI x ROI -> ROI"""
    r = f(dx.val, dy.val)
    sources = combineSources(dx.sources, dy.sources)
    return Datum(Datum.ROI, r, sources)

# end of binop semantics wrappers


def extractChannel(a: Datum, b: Datum) -> Datum:
    """Extract a channel by name from an image, used for the $ operator.
    a: a Datum which must be an image
    b: a Datum which must be an identifier or numeric wavelength
    return: a new single-channel image datum
    """
    img = a.val
    is_scalar = True

    if b.tp == Datum.NUMBER:
        img = img.getChannelImageByFilter(b.val.n)
        is_scalar = b.val.isscalar()
    elif b.tp == Datum.IDENT:
        img = img.getChannelImageByFilter(b.val)
    else:
        raise OperatorException("band extract operator '$' requires ident or numeric wavelength RHS")

    if img is None:
        raise OperatorException("unable to get this wavelength from an image: " + str(b))

    if img.channels > 1 and is_scalar:
        raise OperatorException("'$' has multiple bands in result from a single requested band - does the image have more than one band with the same wavelength/name?")

    img.rois = a.val.rois.copy()
    return Datum(Datum.IMG, img)


def initOps():
    """Initialise functions. Would be in the top-level, but I get
    some spurious warnings."""

    # should be no need to check for None or Datum.NONE here, that will
    # be done in binop() and unop()

    registerUnopSemantics(Operator.NEG, Datum.IMG, lambda datum: imageUnop(datum, lambda x: -x))
    registerUnopSemantics(Operator.NOT, Datum.IMG, lambda datum: imageUnop(datum, lambda x: 1 - x))

    registerUnopSemantics(Operator.NEG, Datum.NUMBER, lambda datum: numberUnop(datum, lambda x: -x))
    registerUnopSemantics(Operator.NOT, Datum.NUMBER, lambda datum: numberUnop(datum, lambda x: ~x))

    def regAllBinopSemantics(op, fn):
        """Used to register binops for types which support all operations, including max and min"""
        registerBinopSemantics(op, Datum.IMG, Datum.IMG, lambda dx, dy: imageBinop(dx, dy, fn))
        registerBinopSemantics(op, Datum.NUMBER, Datum.IMG, lambda dx, dy: numberImageBinop(dx, dy, fn))
        registerBinopSemantics(op, Datum.IMG, Datum.NUMBER, lambda dx, dy: imageNumberBinop(dx, dy, fn))
        registerBinopSemantics(op, Datum.NUMBER, Datum.NUMBER, lambda dx, dy: numberBinop(dx, dy, fn))

    # we COULD just replace the lambdas with Value.__add__ etc, but it's clearer this way.
    regAllBinopSemantics(Operator.ADD, lambda x, y: x + y)
    regAllBinopSemantics(Operator.SUB, lambda x, y: x - y)
    regAllBinopSemantics(Operator.MUL, lambda x, y: x * y)
    regAllBinopSemantics(Operator.DIV, lambda x, y: x / y)
    regAllBinopSemantics(Operator.POW, lambda x, y: x ** y)
    regAllBinopSemantics(Operator.AND, lambda x, y: x & y)
    regAllBinopSemantics(Operator.OR, lambda x, y: x | y)

    def regROIBinopSemantics(op, fn):
        """Used to register binops for ROIs, which support a subset of ops."""
        registerBinopSemantics(op, Datum.ROI, Datum.ROI, lambda dx, dy: ROIBinop(dx, dy, fn))

    regROIBinopSemantics(Operator.ADD, lambda x, y: x + y)
    regROIBinopSemantics(Operator.SUB, lambda x, y: x - y)
    regROIBinopSemantics(Operator.MUL, lambda x, y: x * y)
    regROIBinopSemantics(Operator.DIV, lambda x, y: x / y)
    regROIBinopSemantics(Operator.POW, lambda x, y: x ** y)

    registerUnopSemantics(Operator.NEG, Datum.ROI,
                          lambda d: Datum(Datum.ROI, -d.get(Datum.ROI), d.getSources()))

    registerBinopSemantics(Operator.DOLLAR, Datum.IMG, Datum.NUMBER, extractChannel)
    registerBinopSemantics(Operator.DOLLAR, Datum.IMG, Datum.IDENT, extractChannel)


initOps()
