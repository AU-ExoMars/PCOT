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
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np

import pcot.ui as ui
from pcot import dq
from pcot.ancillary import keys
from pcot.cameras.filters import Filter
from pcot.imagecube import ImageCube


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
    w: int
    h: int
    bands: int
    interleave: str # bsq, bil, bip.
    datatype: type
    defaultBands: Optional[List[int]]
    gains: Optional[List[float]]      # gains to be applied or None
    offsets: Optional[List[float]]  # offsets to be applied or None
    exposureTimes: Optional[List[float]]  # in seconds, or None if not in the file
    filters: List[Filter]
    ignoreValue: Optional[float]
    headerOffset: int   # bytes to skip at the start of the data file


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

        try:
            self.w = int(d['samples'])
            self.h = int(d['lines'])
            self.bands = int(d['bands'])
        except KeyError as e:
            f.close()
            raise Exception(f'ENVI parsing error - key {e.args[0]} not found')

        self.headerOffset = int(d['header offset']) if 'header offset' in d else 0
        self.byteorder = 'little' if ('byte order' not in d) or (d['byte order'] == '0') else 'big'

        if 'interleave' not in d:
            raise Exception('ENVI parsing error: no "interleave" field')
        self.interleave = d['interleave'].lower()
        if self.interleave not in ('bsq', 'bil', 'bip'):
            raise Exception(f"Unknown interleave in ENVI header: {self.interleave}")
        try:
            self.datatype = {
                1: np.uint8,
                2: np.int16,
                3: np.int32,
                4: np.float32,
                5: np.float64,
                12: np.uint16,
                13: np.uint32,
                14: np.int64,
                15: np.uint64,
            }[int(d['data type'])]
        except KeyError as e:
            f.close()
            if 'data type' not in d:
                raise Exception('ENVI parsing error: no "data type" field')
            raise Exception(f"Unknown data type in ENVI header: {d['data type']}")
        except ValueError as e:
            f.close()
            raise Exception(f"Error in ENVI header, data type should be in integer: {d['data type']}")

        if 'default bands' in d:
            # based at one, for heaven's sake.
            self.defaultBands = [int(x) - 1 for x in d['default bands']]
        else:
            self.defaultBands = None

        if 'band names' in d:
            bandNames = d['band names']
        else:
            bandNames = [str(x) for x in range(self.bands)]

        if 'data gain values' in d:
            self.gains = [float(x) for x in d['data gain values']]
        else:
            self.gains = None

        if 'data offset values' in d:
            self.offsets = [float(x) for x in d['data offset values']]
        else:
            self.offsets = None

        if 'exposure times' in d:
            # these are assumed to be in seconds.
            self.exposureTimes = [float(x) for x in d['exposure times']]
        else:
            self.exposureTimes = None

        # per-band lists must have one entry per band
        for name, lst in (('data gain values', self.gains),
                          ('data offset values', self.offsets),
                          ('exposure times', self.exposureTimes)):
            if lst is not None and len(lst) != self.bands:
                raise Exception(f"ENVI header has {len(lst)} {name} but {self.bands} bands")

        if 'wavelength' in d:
            wavelengths = [float(x) for x in d['wavelength']]
            if 'fwhm' in d:
                fwhm = [float(x) for x in d['fwhm']]
            else:
                fwhm = [0 for _ in wavelengths]

            self.filters = []
            for w, f, n in zip(wavelengths, fwhm, bandNames):
                # I'm setting the transmissions to 1 here because any gain value will be applied in the loader.
                self.filters.append(Filter(w, f, 1.0, n, n))
        else:
            # no wavelengths, create dummy filters using the band names if we have them
            if 'band names' not in d:
                bandNames = [f"band {n}" for n in range(self.bands)]
            self.filters = [Filter(0, 0, 1.0, n, n) for n in bandNames]


        if 'data ignore value' in d:
            self.ignoreValue = float(d['data ignore value'])
        else:
            self.ignoreValue = None


def load(fn:Path|str, apply_gain_and_offset:bool=False) -> Tuple[ENVIHeader, np.ndarray, Optional[np.ndarray]]:
    """Takes the ENVI header name. Actually loads the envi, returning a tuple of (header, ndarray, dq).
    The ndarray is (h,w,bands) float32. The dq is a uint16 array of the same shape with NODATA set wherever
    the raw data matches the "data ignore value", or None if there is no ignore value."""

    if not fn:
        raise Exception("No filename given in ENVI load!")
    with open(fn) as f:
        h = ENVIHeader(f)

    (path, _) = os.path.splitext(fn)

    datfile = None
    FILETYPES = ['.img','.dat']
    # so we get [format1,FORMAT1,format2,FORMAT2...]. Nested comprehension.
    FILETYPES = [y for x in FILETYPES for y in (x,x.upper())]

    for x in FILETYPES:
        if os.path.isfile(path + x):
            datfile = path + x
            break

    if datfile is None:
        raise Exception("cannot find ENVI data file")

    # make sure the data is the right size.
    size = os.stat(datfile).st_size
    count = h.bands * h.w * h.h
    # set the byte order on the file's data type so numpy reads it correctly
    dtype = np.dtype(h.datatype).newbyteorder('<' if h.byteorder == 'little' else '>')
    if size != h.headerOffset + dtype.itemsize * count:
        raise Exception("Size of ENVI data file is incorrect")

    # now read the data into a big single array.
    data = np.fromfile(datfile, dtype, count, offset=h.headerOffset)

    # get a boolean mask for where the ignored values are, using the raw values
    if h.ignoreValue is None:
        ignored = None
    elif np.isnan(h.ignoreValue):
        ignored = np.isnan(data)
    else:
        ignored = data == h.ignoreValue

    # convert to native float32
    data = data.astype(np.float32)

    # now process the interleaved data
    def deinterleave(a):
        if h.interleave == "bsq":
            a = a.reshape(h.bands, h.h, h.w).transpose(1, 2, 0)
        elif h.interleave == "bil":
            a = a.reshape(h.h, h.bands, h.w).transpose(0, 2, 1)
        else:   # bip, already in this order
            a = a.reshape(h.h, h.w, h.bands)
        # ensures the data is contiguous in memory but don't reshape to 1D
        return np.ascontiguousarray(a)

    data = deinterleave(data)
    if ignored is not None:
        dqdata = np.where(deinterleave(ignored), dq.NODATA, 0).astype(np.uint16)
    else:
        dqdata = None

    if apply_gain_and_offset:
        if h.gains:
            for band,gain in enumerate(h.gains):
                data[:,:,band] *= gain
        if h.offsets:
            for band,off in enumerate(h.offsets):
                data[:,:,band] += off

    return h, data, dqdata


def _genheader(f, w: int, h: int, freqs: List[float], exp_times: Optional[List[float]] = None, camname="LWAC",):
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
    f.write("wavelength units = nm\n")
    f.write("default stretch = 0.000000000000e+000 1.000000000000e+000 linear\n")
    g = 1.0
    s = ", ".join([f"{g:.4e}" for f in freqs])
    f.write(f"data gain values = {{\n {s}}}\n")
    f.write("calibration target label = MacBeth_ColorChecker\n")
    f.write(f"camera name = {camname}\n")
    f.write("camera system = SIM\n")
    # exposure times (in seconds) are omitted if we don't have them, rather than made up - so
    # they will read back as missing. repr() of a float is the shortest string which reads back
    # as exactly the same value.
    if exp_times is not None:
        s = ", ".join([repr(float(x)) for x in exp_times])
        f.write(f"exposure times = {{\n {s}}}\n")
    f.write("sensor bit-depth = 10\n")
    f.write("session id = testing\n")
    f.write("units = DN/s\n")


def _write(name: str, freqs: List[float], img: np.ndarray, camname, exp_times=None):
    """The input here a filename base, a (h,w,depth) numpy array,
    and a set of frequencies of the same number as the depth."""
    assert (len(img.shape) == 3)
    h, w, depth = img.shape
    assert depth == len(freqs)

    # first, write out the header
    with open(f"{name}.hdr", "w") as f:
        _genheader(f, w, h, freqs, camname=camname, exp_times=exp_times)

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
    exps = img.ancillary.get(keys.EXPOSURE.name)
    if any(x is None for x in exps):
        exps = None

    _write(fn, freqs, img.img, camname, exps)
