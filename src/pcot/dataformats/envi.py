##
# Portions of the code below are modified from spectralpython,
# Copyright (C) 2002 Thomas Boggs; license follows:

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions: 

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE. 

import os
import sys
from typing import List

import numpy as np

import pcot.ui as ui
from pcot.filters import Filter
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.sources import InputSource, MultiBandSource


def parseHeader(lines):
    d = {}
    have_nonlowercase_param = False
    try:
        while lines:
            line = lines.pop(0)
            if line.find('=') == -1:
                continue
            if line[0] == ';':
                continue

            (key, sep, val) = line.partition('=')
            key = key.strip()
            if not key.islower():
                have_nonlowercase_param = True
                key = key.lower()
            val = val.strip()
            if val and val[0] == '{':
                ss = val.strip()
                while ss[-1] != '}':
                    line = lines.pop(0)
                    if line[0] == ';': continue

                    ss += '\n' + line.strip()
                if key == 'description':
                    d[key] = ss.strip('{}').strip()
                else:
                    vals = ss[1:-1].split(',')
                    for j in range(len(vals)):
                        vals[j] = vals[j].strip()
                    d[key] = vals
            else:
                d[key] = val

        if have_nonlowercase_param:
            ui.warn('Parameters with non-lowercase names encountered '
                    'and converted to lowercase.')
        return d
    except:
        raise Exception('ENVI parsing error')


class ENVIHeader:
    def __init__(self, f):
        try:
            isENVI = f.readline().strip().startswith('ENVI')
        except UnicodeDecodeError:
            f.close()
            raise Exception('File is not an ENVI header (is binary file?)')
        else:
            if not isENVI:
                f.close()
                raise Exception('File is not an ENVI file (no "ENVI" on first line)')

        lines = f.readlines()
        f.close()
        d = parseHeader(lines)

        # get the important data out into fields

        # some odd nomeclature I will accept, but calling "width" and
        # "height" by these names seems needlessly obtuse.

        self.w = int(d['samples'])
        self.h = int(d['lines'])
        self.bands = int(d['bands'])

        self.headerOffset = [int(d['headerOffset']) if 'headerOffset' in d else 0]
        self.byteorder = 'little' if d['byte order'] == '0' else 'big'

        if d['interleave'] != 'bsq':
            raise Exception("Only BSQ interleave is supported")
        if d['data type'] != '4':
            raise Exception("Data type must be 32-bit float")

        if 'default bands' in d:
            # based at one, for heaven's sake.
            self.defaultBands = [int(x)-1 for x in d['default bands']]
        else:
            self.defaultBands = [0, 1, 2]

        if 'band names' in d:
            bandNames = d['band names']
        else:
            bandNames = [str(x) for x in range(self.bands)]

        if 'wavelength' in d:
            wavelengths = [float(x) for x in d['wavelength']]
            if 'fwhm' in d:
                fwhm = [float(x) for x in d['fwhm']]
            else:
                fwhm = [0 for _ in wavelengths]

            if 'data gain values' in d:
                gain = [float(x) for x in d['data gain values']]
            else:
                gain = [0 for _ in wavelengths]

            self.gains = gain

            self.filters = []
            for w, f, g, n in zip(wavelengths, fwhm, gain, bandNames):
                self.filters.append(Filter(w, f, g, n, n))

        if 'data ignore value' in d:
            self.ignoreValue = float(d['data ignore value'])
        else:
            self.ignoreValue = None


def _load(fn):
    """Takes the ENVI header name. Actually loads the envi, returning a tuple of (header, ndarray)"""
    with open(fn) as f:
        h = ENVIHeader(f)

    (path, _) = os.path.splitext(fn)

    datfile = None
    for x in ['.img', '.dat', '.IMG', '.DAT']:
        if os.path.isfile(path + x):
            datfile = path + x
            break

    if datfile is None:
        raise Exception("cannot find ENVI data file")

    size = os.stat(datfile).st_size

    # remember, we only support float format BSQ right now.

    requiredSize = 4 * h.bands * h.w * h.h

    if size != requiredSize:
        raise Exception("Size of ENVI data file is incorrect")

    bands = []
    with open(datfile, "rb") as f:
        for i in range(0, h.bands):
            band = np.fromfile(f, np.float32, h.w * h.h).reshape(h.h, h.w)
            gain = h.gains[i]
            if sys.byteorder != h.byteorder:
                band = band.byteswap()
            bands.append(band)      # Do I need to apply the data gain values here??

    # now have list of 6 bands. Interleave.
    img = np.stack(bands, axis=-1)

    return h, img


def load(fn, doc, inpidx, mapping: ChannelMapping = None) -> ImageCube:
    """Load a file as an ENVI. The filename is the header filename (.hdr).
    Requires a Document and an input index, so don't call this directly - Document.setInputENVI()."""

    # perform cached load
    h, img = _load(fn)

    # construct the source data
    sources = MultiBandSource([InputSource(doc, inpidx, f) for f in h.filters])

    if mapping is None:
        mapping = ChannelMapping()
    mapping.set(*h.defaultBands)
    return ImageCube(img, mapping, sources, defaultMapping=mapping.copy())


def _genheader(f, w: int, h: int, freqs: List[float],camname="LWAC"):
    """Crude envi header writer"""
    
    f.write("ENVI\n")
    f.write(f"samples = {w}\nlines   = {h}\nbands   = {len(freqs)}\n")
    f.write("data type = 4\ninterleave = bsq\nfile type = ENVI Standard\n")
    f.write("header offset = 0\nbyte order = 0\n")
    f.write("geo points = {\n")
    f.write(f"    0.00000000,    0.00000000,    0.00000000,    0.00000000,\n")
    f.write(f" {w - 1}.00000000,    0.00000000,    0.00000000, {w - 1}.00000000,\n")
    f.write(f"    0.00000000, {h - 1}.00000000, {h - 1}.00000000,    0.00000000,\n")
    f.write(f" {w - 1}.00000000, {h - 1}.00000000, {w - 1}.00000000, {h - 1}.00000000}}\n")

#    defbands = [min(x, len(freqs)) for x in [1, 2, 3]]
#    s = ",".join([str(x) for x in defbands])
#    f.write(f"default bands = {{{s}}}\n")
    bandnames = ", ".join([f"L{i + 1}_{f}" for i, f in enumerate(freqs)])
    f.write(f"band names = {{\n {bandnames}}}\n")
    s = ", ".join([f"{f:0.6f}" for f in freqs])
    f.write(f"wavelength = {{\n {s}}}\n")
    fwhm = 25
    s = ", ".join([f"{fwhm:0.6f}" for f in freqs])
    f.write(f"fwhm = {{\n {s}}}\n")
    f.write("wavelength units = nm\ndata ignore value = 241.000000\n")
    f.write("default stretch = 0.000000000000e+000 1.000000000000e+000 linear\n")
    g = 1.0
    s = ", ".join([f"{g:.4e}" for f in freqs])
    f.write(f"data gain values = {{\n {s}}}\n")
    f.write("calibration target label = MacBeth_ColorChecker\n")
    f.write(f"camera name = {camname}\n")
    f.write("camera system = SIM\n")
    t = 0.01
    s = ", ".join([f"{t:0.2f}" for f in freqs])
    f.write(f"exposure times = {{\n {s}}}\n")
    f.write("sensor bit-depth = 10\n")
    f.write("session id = testing\n")
    f.write("units = DN/s\n")


def _write(name: str, freqs: List[float], img: np.ndarray, camname):
    """The input here a filename base, a (h,w,depth) numpy array,
    and a set of frequencies of the same number as the depth."""
    assert (len(img.shape) == 3)
    h, w, depth = img.shape
    assert depth == len(freqs)

    # first, write out the header
    with open(f"{name}.hdr", "w") as f:
        _genheader(f, w, h, freqs,camname)

    # now output the actual ENVI data
    bands = [np.reshape(x, img.shape[:2]) for x in np.dsplit(img, img.shape[-1])]
    with open(f"{name}.dat", "wb") as f:
        for b in bands:
            assert b.shape == img.shape[:2]
            data = b.reshape(w * h).astype(np.float32)
            f.write(data)


def write(fn: str, img: ImageCube, camname="LWAC"):
        # convert the sources to frequencies, assuming there is only
        # one source per channel and they all have centre wavelength values
        freqs = [next(iter(s)).getFilter().cwl for s in img.sources]

        _write(fn, freqs, img.img, camname)
