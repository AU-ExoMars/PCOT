import hashlib
import numpy as np
from pathlib import Path


class BayerSlice:
    """The `BayerSlice` class carries `slice` attributes targeting individual Bayer
    channels for a given pattern and (subframe) origin offset.

    Attributes:
        r: `slice` identifying red channel pixels
        g1: `slice` identifying first green channel pixels
        g2: `slice` identifying second green channel pixels
        b: `slice` identifying blue channel pixels
        pattern: effective pattern given the offset (upper case)
    """

    def __init__(self, pattern: str, y_off: int = 0, x_off: int = 0) -> None:
        """
        Args:
            pattern: one of "RGGB", "BGGR", "GRBG", or "GBRG"; arrangement of the
                colour channels
            y_off: optional y-axis (lines) subframe offset to account for
            x_off: optional x-axis (samples) subframe offset to account for
        """
        pattern = pattern.lower()
        if not sorted(pattern) == ["b", "g", "g", "r"]:
            raise ValueError(f"Invalid bayer pattern: '{pattern}'")

        self.r: slice = None
        self.g1: slice = None
        self.g2: slice = None
        self.b: slice = None

        y = 0
        x = 1
        loc_order = ((0, 0), (0, 1), (1, 0), (1, 1))
        loc_mod = (y_off % 2, x_off % 2)

        reordered = [""] * 4
        g_count = 1
        for i, c in enumerate(pattern):
            if c == "g":
                c = f"g{g_count}"
                g_count += 1
            loc = (
                (loc_order[i][y] + loc_mod[y]) % 2,
                (loc_order[i][x] + loc_mod[x]) % 2,
            )
            self.__setattr__(c, np.s_[loc[y] :: 2, loc[x] :: 2])
            reordered[loc_order.index(loc)] = c[0].upper()
        self.pattern: str = "".join(reordered)


def get_md5sum(path: Path, buffer: int = 128 * 1024):
    """Generate the md5 hash for a file in chunks, providing a low memory footprint"""
    md5 = hashlib.md5()
    with open(path, "rb", buffering=0) as f:
        while True:
            data = f.read(buffer)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()
