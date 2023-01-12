"""Definitions of bits in the DQ data. These are bit values. so powers of two!"""

DQs = dict()            # dictionary of name->poweroftwo gets created by calls to reg


def reg(name, bit):
    global DQs
    b = 1 << bit
    DQs[name] = b
    return b


NODATA = reg('nodata', 0)               # Pixel has no data
NOUNCERTAINTY = reg('nounc', 1)         # Pixel has no uncertainty information.
SAT = reg('sat', 2)                     # Pixel is saturated high
TEST = reg('test', 4)
