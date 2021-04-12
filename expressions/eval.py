# This is the application-specific part of the expression parsing system.
# In this system, all data is a Datum object.
import conntypes
from expressions import parse
from expressions.parse import Stack
from utils.binop import binop
from xform import Datum

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


class Parser(parse.Parser):
    def __init__(self):
        super().__init__(True)  # naked identifiers permitted
        self.registerNumInstFactory(lambda x: InstNumber(x))  # make sure we stack numbers as Datums
        self.registerBinop('+', 10, lambda a, b: binop(a, b, lambda x, y: x + y, None))
        self.registerBinop('-', 10, lambda a, b: binop(a, b, lambda x, y: x - y, None))
        self.registerBinop('/', 20, lambda a, b: binop(a, b, lambda x, y: x / y, None))
        self.registerBinop('*', 20, lambda a, b: binop(a, b, lambda x, y: x * y, None))

    def run(self, s):
        self.parse(s)

        stack = []
        return parse.execute(self.output, stack)
