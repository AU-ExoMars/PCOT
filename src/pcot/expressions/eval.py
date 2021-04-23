# This is the application-specific part of the expression parsing system.
# In this system, all data is a Datum object.
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


def getProperty(a: Datum, b: Datum):
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

        self.registerUnop('-', 50, lambda x: unop(x, lambda a: -a, None))

        self.registerBinop('$', 90, extractChannelByName)
        self.registerBinop('.', 80, getProperty)

        # additional functions
        operations.registerOpFunctions(self)

    def run(self, s):
        self.parse(s)

        stack = []
        return parse.execute(self.output, stack)
