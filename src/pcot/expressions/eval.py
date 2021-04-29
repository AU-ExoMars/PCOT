# This is the application-specific part of the expression parsing system.
# In this system, all data is a Datum object.
from typing import Callable, Dict, Tuple

import numpy as np

import pcot.conntypes as conntypes
import pcot.operations as operations
from pcot.expressions import parse
from pcot.expressions.parse import Stack
from pcot.utils.ops import binop, unop
from pcot.xform import Datum, XFormException


# TODO: error if output is wrong type. Show output in canvas (and other output somehow if not image?). Honour the ROI from the "leftmost" image with an ROI - So A has priority over B, etc.
# TODO: Band selection and combining. Unaries. Expression guide in help.
# TODO: Obviously functions and that.


class InstNumber(parse.Instruction):
    val: float

    def __init__(self, v: float):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(conntypes.NUMBER, self.val))

    def __str__(self):
        return "NUM {}".format(self.val)


class InstIdent(parse.Instruction):
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
    pass


class Parser(parse.Parser):
    def __init__(self):
        super().__init__(True)  # naked identifiers permitted
        self.registerNumInstFactory(lambda x: InstNumber(x))  # make sure we stack numbers as Datums
        self.registerIdentInstFactory(lambda x: InstIdent(x))  # identifiers too
        self.registerBinop('+', 10, lambda a, b: binop(a, b, lambda x, y: x + y, None))
        self.registerBinop('-', 10, lambda a, b: binop(a, b, lambda x, y: x - y, None))
        self.registerBinop('/', 20, lambda a, b: binop(a, b, lambda x, y: x / y, None))
        self.registerBinop('*', 20, lambda a, b: binop(a, b, lambda x, y: x * y, None))
        self.registerBinop('^', 30, lambda a, b: binop(a, b, lambda x, y: x ** y, None))

        self.registerUnop('-', 50, lambda x: unop(x, lambda a: -a, None))

        self.registerBinop('$', 90, extractChannelByName)
        self.registerBinop('.', 100, getProperty)
        self.registerFunc("merge", funcMerge)

        # additional functions
        operations.registerOpFunctionsAndProperties(self)

        # properties - SEE ALSO the __init__.py in the operations module.

        registerProperty('w', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.w))
        registerProperty('h', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.h))
        registerProperty('min', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.func(np.min)))
        registerProperty('max', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.func(np.max)))
        registerProperty('sd', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.func(np.std)))
        registerProperty('mean', conntypes.IMG, lambda x: Datum(conntypes.NUMBER, x.val.func(np.mean)))

    def run(self, s):
        self.parse(s)

        stack = []
        return parse.execute(self.output, stack)
