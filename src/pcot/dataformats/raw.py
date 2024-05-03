"""Loading 'raw' files into an ImageCube object."""
import numpy as np
import os
import logging

from PySide2.QtWidgets import QDialog

from pcot.ui import uiloader

logger = logging.getLogger(__name__)

class RawLoader:
    """Class for loading raw files."""

    # underlying formats
    FLOAT32 = 0
    UINT16 = 1
    UINT8 = 2
    FORMAT_NAMES = ['f32', 'u16', 'u8']

    # we currently assume that the image is a single channel, but this could be extended to multiple channels.
    # We'd have to add depth and interleaving parameters to the constructor.

    format: int  # one of the above values
    width: int  # width of the image
    height: int  # height of the image
    bigendian: bool  # whether the data is big-endian
    offset: int  # size of the header in bytes (this is skipped)
    rot: int  # counter-clockwise rotation of the image in 90 degree steps
    horzflip: bool  # whether the image is flipped horizontally (after rotation)
    vertflip: bool  # whether the image is flipped vertically (after rotation)

    SERIALISE = (
        ('format', UINT16),
        ('width', 1024),
        ('height', 1024),
        ('bigendian', False),
        ('offset', 0),
        ('rot', 0),
        ('horzflip', False),
        ('vertflip', False)
    )

    def __init__(self, format=UINT16, width=1024, height=1024, bigendian=False, offset=0,
                 rot=0, horzflip=False, vertflip=False):
        self.format = format
        self.width = width
        self.height = height
        self.bigendian = bigendian
        self.offset = offset
        self.rot = rot
        self.horzflip = horzflip
        self.vertflip = vertflip

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
            dtype = np.uint16
            scale = 1.0 / 65535.0
        elif self.format == RawLoader.UINT8:
            dtype = np.uint8
            scale = 1.0 / 255.0
        else:
            raise ValueError(f"Unknown format {self.format}")
        data = np.fromfile(filename, dtype=dtype, offset=self.offset)
        if self.bigendian:
            data.byteswap(True)
        data = data.reshape(self.height, self.width)
        data = np.rot90(data, int(self.rot/90))
        if self.horzflip:
            data = np.fliplr(data)
        if self.vertflip:
            data = np.flipud(data)

        # convert to float32 if necessary, dividing down to the range 0-1
        if dtype != np.float32:
            logger.info(f"Loading data, currently the range is {data.min()} to {data.max()}, format is {dtype}")
            data = data.astype(np.float32) * scale
            logger.info(f"Loaded as F32. Range is now {data.min()} to {data.max()}")
        return data

    @staticmethod
    def is_raw_file(path):
        """Is this a raw file? Used to determine whether to use this loader
        or the standard RGB loader in ImageCube"""
        ext = os.path.splitext(path)[1].lower()
        return ext in ('.raw', '.bin')
    
    def __str__(self):
        """Produce a string representation of the loader."""
        formatname = self.FORMAT_NAMES[self.format]
        bigendian = 'BE' if self.bigendian else 'LE'
        flip = 'HV' if self.horzflip and self.vertflip else 'H' if self.horzflip else 'V' if self.vertflip else None
        flip = f"flip {flip}" if flip else ''
        rot = f"rot {self.rot}CCW" if self.rot else ''
        return f"{formatname} {self.width}x{self.height}+{self.offset} {bigendian} {rot} {flip}"

    def edit(self, parent):
        """Opens a dialog to edit the parameters of the loader."""
        dlg = RawLoaderDialog(parent, self)
        if dlg.exec():
            dlg.setLoader(self)


class RawLoaderDialog(QDialog):
    """Dialog to set the parameters for the raw loader."""
    def __init__(self, parent, loader):
        super().__init__(parent)
        uiloader.loadUi('rawloader.ui', self)

        self.formatCombo.setCurrentIndex(loader.format)
        self.widthSpin.setValue(loader.width)
        self.heightSpin.setValue(loader.height)
        self.bigendianCheck.setChecked(loader.bigendian)
        self.headerSpin.setValue(loader.offset)
        self.vertCheck.setChecked(loader.vertflip)
        self.horzCheck.setChecked(loader.horzflip)
        self.rotSpin.setValue(loader.rot)

    def setLoader(self, loader):
        loader.format = self.formatCombo.currentIndex()
        loader.width = self.widthSpin.value()
        loader.height = self.heightSpin.value()
        loader.bigendian = self.bigendianCheck.isChecked()
        loader.offset = self.headerSpin.value()
        loader.vertflip = self.vertCheck.isChecked()
        loader.horzflip = self.horzCheck.isChecked()
        loader.rot = self.rotSpin.value()
