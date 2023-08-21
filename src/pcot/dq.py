"""Definitions of bits in the DQ data. These are bit values. so powers of two!"""
import dataclasses

import numpy as np

from pcot.utils.table import Table

DQs = dict()  # dictionary of name->poweroftwo gets created by calls to reg
defs = dict()  # poweroftwo->data

NUMBITS = 16

@dataclasses.dataclass
class DQDefinition:
    name: str
    bit: np.uint16
    desc: str
    char: str


def reg(name, bit, char, desc):
    global DQs, defs
    b = np.uint16(1 << bit)

    d = DQDefinition(name, b, desc, char)

    DQs[name] = b
    defs[b] = d
    return b        # return bit value


def names(bits, shownone=False):
    """given a DQ bit field, return the names of the set flags"""
    if shownone and bits == 0:
        return "none"
    out = []
    for i in range(0, NUMBITS):
        b = 1 << i
        if (b & bits) != 0:
            out.append(defs[b].name if b in defs else f"??{b}??")
    return "|".join(out)


def chars(bits, shownone=False):
    """given a DQ bit field, return the character string for those bits (i.e. very terse description)"""
    if shownone and bits == 0:
        return "none"
    out = ""
    for i in range(0, NUMBITS):
        b = 1 << i
        if (b & bits) != 0:
            out += defs[b].char if b in defs else f"|{b}|"
    return out


def listBits():
    global defs
    t = Table()
    for bit, d in defs.items():
        t.newRow()
        t.add("name", d.name)
        t.add("mask", d.bit)
        t.add("code", d.char)
        t.add("description", d.desc)
        t.add("is BAD (i.e. an error)?", "YES" if d.bit & BAD != 0 else "")
    return t.markdown()


# Note that 'pixel is...' can mean indirectly, so 'pixel is divided by zero' means that the pixel
# is the result of a chain of calculations that involved a division by zero at some point.

NODATA = reg('nodata', 0, 'D', "Pixel has no data")
NOUNCERTAINTY = reg('nounc', 1, 'u', "Pixel has no uncertainty information")
SAT = reg('sat', 2, 's', "Pixel is saturated")
DIVZERO = reg('divzero', 3, 'Z', "Pixel data is result of divided by zero")
UNDEF = reg('undefined', 4, '?', "Pixel data is undefined result")
COMPLEX = reg('complex', 5, 'C', "Pixel data is result of calculation with complex result")
ERROR = reg('error', 6, 'E', "Pixel data has unspecified error")

NONE = np.uint16(0)

TEST = reg('test', 15, 'T', "Pixel data has test bit set")

MAX = 65535


# Pixels with these bits are considered bad and are not to be used in aggregate calculations
# like mean, std.
BAD = NODATA | SAT | DIVZERO | UNDEF | COMPLEX | ERROR
