"""binary and unary operations which work on many kinds of data sensibly."""
from enum import Enum, auto
from typing import Any, Callable, Optional, Dict, Tuple

import numpy as np

from pcot import number
from pcot import dq
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
    return MultiBandSource([SourceSet(x.sourceSet.union(other.sourceSet)) for x in img.sources.sourceSets])


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


def combineDQs(a, b, extra=None):
    """Bitwise OR DQs together. A and B are the DQs of the two data we're combining, which the result
    should inherit. Extra is any extra bits that need to be set."""
    if a.dq is None:
        r = b.dq
    elif b.dq is None:
        r = a.dq
    else:
        r = a.dq | b.dq

    # if r is a zero-dimensional array, convert it

    if extra is not None:
        # first, extra *could* be a 0-dimensional array because of how np.where works on scalar inputs
        if extra.shape == ():
            extra = int(extra)
        else:
            # if it isn't, it could well be the wrong integer type - so convert it to the correct one.
            extra = extra.astype(np.uint16)
        if r is None:
            r = extra
        else:
            r |= extra

    return r


def reduce_if_zero_dim(n):
    if not np.isscalar(n):
        n = n[()]
    return n


EPSILON = 0.00001


class OpData:
    """Class used to pass data into and out of uncertainty/DQ-aware binops and wrap the operations,
    because the dunders used in Number aren't enough."""

    def __init__(self, n, u, dq=0):
        self.n = n  # nominal, either float or ndarray
        self.u = u  # uncertainty, either float or ndarray
        self.dq = dq  # if a result, the DQ bits. May be zero, shouldn't be None.

    def copy(self):
        return OpData(self.n, self.u, self.dq)

    def serialise(self):
        return self.n, self.u, self.dq

    @staticmethod
    def deserialise(t):
        n, u, d = t
        return OpData(n, u, d)

    def __eq__(self, other):
        if not isinstance(other, OpData):
            return False
        aa = self.n == other.n
        bb = self.u == other.u

        return self.n == other.n and self.u == other.u and self.dq == other.dq

    def approxeq(self, other):  # used in tests
        return abs(self.n - other.n) < EPSILON and abs(self.u - other.u) < EPSILON and self.dq == other.dq

    def __add__(self, other):
        return OpData(self.n + other.n, number.add_sub_unc(self.u, other.u),
                      combineDQs(self, other))

    def __sub__(self, other):
        return OpData(self.n - other.n, number.add_sub_unc(self.u, other.u),
                      combineDQs(self, other))

    def __mul__(self, other):
        return OpData(self.n * other.n, number.mul_unc(self.n, self.u, other.n, other.u),
                      combineDQs(self, other))

    def __truediv__(self, other):
        try:
            n = np.where(other.n == 0, 0, self.n / other.n)
            u = np.where(other.n == 0, 0, number.div_unc(self.n, self.u, other.n, other.u))
            d = combineDQs(self, other, np.where(other.n == 0, dq.DIVZERO, dq.NONE))
            # fold zero dimensional arrays (from np.where) back into scalars
            n = reduce_if_zero_dim(n)
            u = reduce_if_zero_dim(u)
            d = reduce_if_zero_dim(d)
        except ZeroDivisionError:
            # should only happen where we're dividing scalars
            n = 0
            u = 0
            d = self.dq | other.dq | dq.DIVZERO
        return OpData(n, u, d)

    def __pow__(self, power, modulo=None):
        # zero cannot be raised to -ve power so invalid, but we use zero as a dummy.
        try:
            n = np.where((self.n == 0.0) & (power.n < 0), 0, self.n ** power.n)
            u = np.where((self.n == 0.0) & (power.n < 0), 0, number.pow_unc(self.n, self.u, power.n, power.u))
            d = combineDQs(self, power, np.where((self.n == 0.0) & (power.n < 0), dq.UNDEF, dq.NONE))
            # remove imaginary component of complex result but mark as complex in DQ
            qq = np.where(n.imag != 0.0, dq.COMPLEX, dq.NONE)
            d |= qq
            n = n.real
            # and fold zerodim arrays back to scalar
            n = reduce_if_zero_dim(n)
            u = reduce_if_zero_dim(u)
            d = reduce_if_zero_dim(d)
        except ZeroDivisionError:
            # should only happen where we're processing scalars
            n = 0
            u = 0
            d = self.dq | power.dq | dq.UNDEF
        return OpData(n, u, d)

    def __and__(self, other):
        """The & operator actually finds the minimum (Zadeh op)"""
        n = np.where(self.n > other.n, other.n, self.n)
        u = np.where(self.n > other.n, other.u, self.u)
        d = np.where(self.n > other.n, other.dq, self.dq)
        return OpData(n, u, d)

    def __or__(self, other):
        """The & operator actually finds the maximum (Zadeh op)"""
        n = np.where(self.n < other.n, other.n, self.n)
        u = np.where(self.n < other.n, other.u, self.u)
        d = np.where(self.n < other.n, other.dq, self.dq)
        return OpData(n, u, d)

    def __neg__(self):
        return OpData(-self.n, self.u, self.dq)

    def __invert__(self):
        return OpData(1 - self.n, self.u, self.dq)

    def __str__(self):
        if np.isscalar(self.n):
            names = dq.names(self.dq)
            return f"Value:{self.n}±{self.u}{names}"
        else:
            return f"Value:array{self.n.shape}"

    def __repr__(self):
        return self.__str__()

# TODO UNCERTAINTY - work out what the args should be and pass them in
def numberImageBinop(dx: Datum, dy: Datum, f: Callable[[OpData, OpData], OpData]) -> Datum:
    """This wraps binary operations number x imagecube"""
    # get the image
    img = dy.val
    # create a subimage
    subimg = img.subimage()
    # get the uncertainty-aware forms of the operands
    a = OpData(dx.val.n, dx.val.u)
    b = OpData(subimg.masked(), subimg.maskedUncertainty())
    # perform the operation
    r = f(a, b)
    # put the result back into the image
    img = img.modifyWithSub(subimg, r.n, uncertainty=r.u, dqOR=r.dq)
    # handle ROIs and sources
    img.rois = dy.val.rois.copy()
    img.sources = combineImageWithNumberSources(img, dx.getSources())
    return Datum(Datum.IMG, img)


# TODO UNCERTAINTY - work out what the args should be and pass them in
def imageNumberBinop(dx: Datum, dy: Datum, f: Callable[[OpData, OpData], OpData]) -> Datum:
    """This wraps binary operations imagecube x number"""
    img = dx.val  # Datum.IMG
    subimg = img.subimage()
    a = OpData(subimg.masked(), subimg.maskedUncertainty())
    b = OpData(dy.val.n, dy.val.u)
    r = f(a, b)
    img = img.modifyWithSub(subimg, r.n, uncertainty=r.u, dqOR=r.dq)
    img.rois = dx.val.rois.copy()
    img.sources = combineImageWithNumberSources(img, dy.getSources())
    return Datum(Datum.IMG, img)


# TODO UNCERTAINTY - work out what the args should be and pass them in
def numberBinop(dx: Datum, dy: Datum, f: Callable[[Number, Number], Number]) -> Datum:
    """Wraps number x number -> number"""
    r = f(dx.val, dy.val)
    return Datum(Datum.NUMBER, r, SourceSet([dx.getSources(), dy.getSources()]))


def ROIBinop(dx: Datum, dy: Datum, f: Callable[[ROI, ROI], ROI]) -> Datum:
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
