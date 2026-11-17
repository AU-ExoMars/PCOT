"""
Tests for using PCOT from Jupyter notebooks: images displaying themselves, and PCOT not taking
over the logging configuration of a program which imports it.
"""
import logging
import struct

import pcot
from fixtures import *
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.rois import ROICircle
from pcot.sources import nullSourceSet
from pcot.value import Value

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(data):
    """width and height from the IHDR chunk, which always follows the signature"""
    return struct.unpack(">II", data[16:24])


def test_imagecube_repr_png():
    """An ImageCube gives PNG data for notebooks to display, scaled up to the minimum notebook width
    with the aspect ratio kept"""
    img = genrgb(50, 40, 0.2, 0.5, 0.8)
    img.rois.append(ROICircle(20, 20, 8, label="spot"))
    data = img._repr_png_()
    assert data.startswith(PNG_SIGNATURE)
    w, h = png_size(data)
    assert w == ImageCube.NOTEBOOK_MIN_WIDTH
    assert h == round(w * 40 / 50)


def test_imagecube_repr_png_large_image_keeps_width():
    """Images wider than the notebook minimum are shown at their own width"""
    big = ImageCube.NOTEBOOK_MIN_WIDTH + 100
    data = genrgb(big, 10, 0.1, 0.1, 0.1)._repr_png_()
    assert png_size(data)[0] == big


def test_datum_repr_png():
    """Image Datums display as their image; other Datums give None, so the text form is used"""
    img = genrgb(30, 20, 0.5, 0.5, 0.5)
    assert Datum(Datum.IMG, img)._repr_png_() == img._repr_png_()
    assert Datum(Datum.NUMBER, Value(1.0, 0.0), nullSourceSet)._repr_png_() is None


def test_import_does_not_configure_logging():
    """Importing PCOT mustn't set up the root logger, or set the pcot logger's level - that's left to
    the program using it (the pcot and pcotbatch commands call pcot.setupLogging() and set a level)"""
    pcotformat = '%(levelname)s %(asctime)s %(name)s: %(message)s'
    for h in logging.getLogger().handlers:
        assert h.formatter is None or h.formatter._fmt != pcotformat
    assert pcot.logger.level == logging.NOTSET


def test_setup_leaves_root_logger_alone():
    """pcot.setup() must leave the root logger without handlers. Calls like logging.debug(...) on the
    root logger add one silently, but pytest gives the root logger its own handlers, which would hide
    that here - so this runs in a separate Python process."""
    import subprocess
    import sys
    code = ("import logging, pcot; pcot.setup(); "
            "print(len(logging.getLogger().handlers))")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "0"
