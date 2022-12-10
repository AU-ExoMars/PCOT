"""Definitions of bits in the DQ data. These are bit values. so powers of two!"""


NODATA = 1 << 0                 # Pixel has no data
NOUNCERTAINTY = 1 << 1          # Pixel has no uncertainty information.
SAT = 1 << 2                    # Pixel is saturated high
