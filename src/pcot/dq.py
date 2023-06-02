"""Definitions of bits in the DQ data. These are bit values. so powers of two!"""

DQs = dict()  # dictionary of name->poweroftwo gets created by calls to reg
namedict = dict()  # poweroftwo->name


def reg(name, bit):
    global DQs
    b = 1 << bit
    DQs[name] = b
    namedict[b] = name
    return b


def names(bits):
    """given a DQ bit field, return the names of the set flags"""
    out = []
    for i in range(0, 16):
        b = 1 << i
        if (b & bits) != 0:
            out.append(namedict[b])
    return "|".join(out)


# Note that 'pixel is...' can mean indirectly, so 'pixel is divided by zero' means that the pixel
# is the result of a chain of calculations that involved a division by zero at some point.

NODATA = reg('nodata', 0)  # Pixel has no data
NOUNCERTAINTY = reg('nounc', 1)  # Pixel has no uncertainty information.
SAT = reg('sat', 2)  # Pixel is saturated high
DIVZERO = reg('divzero', 3)     # Pixel is divided by zero


TEST = reg('test', 15)
