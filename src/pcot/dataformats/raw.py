"""Loading 'raw' files into an ImageCube object."""
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

class RawLoader:
    """Class for loading raw files."""

    # underlying formats
    FLOAT32 = 0
    UINT16 = 1
    UINT8 = 2

    # we currently assume that the image is a single channel, but this could be extended to multiple channels.
    # We'd have to add depth and interleaving parameters to the constructor.

    format: int  # one of the above values
    width: int  # width of the image
    height: int  # height of the image
    bigendian: bool  # whether the data is big-endian
    headersize: int  # size of the header in bytes (this is skipped)

    SERIALISE = (
        ('format', UINT16),
        ('width', 1024),
        ('height', 1024),
        ('bigendian', False),
        ('headersize', 0)
    )

    def __init__(self, format=UINT16, width=1024, height=1024, bigendian=False, headersize=0):
        self.format = format
        self.width = width
        self.height = height
        self.bigendian = bigendian
        self.headersize = headersize

    def serialise(self) -> dict:
        return {k: getattr(self, k) for k, _ in self.SERIALISE}

    def deserialise(self, d: dict):
        for k, v in self.SERIALISE:
            setattr(self, k, d.get(k, v))

    def load(self, filename: str) -> np.ndarray:
        """Loads the raw file and returns an array object."""
        if self.format == RawLoader.FLOAT32:
            dtype = np.float32
            scale = 1.0
        elif self.format == RawLoader.UINT16:
            dtype = np.int16
            scale = 1.0 / 65535.0
        elif self.format == RawLoader.UINT8:
            dtype = np.uint8
            scale = 1.0 / 255.0
        else:
            raise ValueError(f"Unknown format {self.format}")
        data = np.fromfile(filename, dtype=dtype, offset=self.headersize)
        if self.bigendian:
            data.byteswap(True)
        data = data.reshape(self.height, self.width)
        data = np.rot90(data, 1)

        # convert to float32 if necessary, dividing down to the range 0-1
        if dtype != np.float32:
            logger.info(f"Loading data, currently the range is {data.min()} to {data.max()}, format is {dtype}")
            data = data.astype(np.float32) * scale
            logger.info(f"Loaded as F32. Range is now {data.min()} to {data.max()}")
        return data

    @staticmethod
    def is_raw_file(path):
        # get extension using os.path.splitext()
        ext = os.path.splitext(path)[1].lower()
        return ext in ('.raw', '.bin')






