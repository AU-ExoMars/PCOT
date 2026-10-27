import numpy as np
from typing import List


def _genheader(f, w: int, h: int, freqs: List[float]):
    f.write("ENVI\n")
    f.write(f"samples = {w}\nlines   = {h}\nbands   = {len(freqs)}\n")
    f.write("data type = 4\ninterleave = bsq\nfile type = ENVI Standard\n")
    f.write("header offset = 0\nbyte order = 0\n")
    f.write("geo points = {\n")
    f.write(f"    0.00000000,    0.00000000,    0.00000000,    0.00000000,\n")
    f.write(f" {w - 1}.00000000,    0.00000000,    0.00000000, {w - 1}.00000000,\n")
    f.write(f"    0.00000000, {h - 1}.00000000, {h - 1}.00000000,    0.00000000,\n")
    f.write(f" {w - 1}.00000000, {h - 1}.00000000, {w - 1}.00000000, {h - 1}.00000000}}\n")

    defbands = [min(x, len(freqs)) for x in [1, 2, 3]]
    s = ",".join([str(x) for x in defbands])
    f.write(f"default bands = {{{s}}}\n")
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
    f.write("camera name = LWAC\n")
    f.write("camera system = SIM\n")
    # no exposure times - they would be read as real ancillary data
    f.write("sensor bit-depth = 10\n")
    f.write("session id = testing\n")
    f.write("units = DN/s\n")


def gen_envi(name: str, freqs: List[float], img: np.ndarray):
    """The input here a filename base, a (h,w,depth) numpy array,
    and a set of frequencies of the same number as the depth."""
    assert (len(img.shape) == 3)
    h, w, depth = img.shape
    assert depth == len(freqs)

    # first, write out the header
    with open(f"{name}.hdr", "w") as f:
        _genheader(f, w, h, freqs)

    # now output the actual ENVI data
    bands = [np.reshape(x, img.shape[:2]) for x in np.dsplit(img, img.shape[-1])]
    with open(f"{name}.dat", "wb") as f:
        for b in bands:
            assert b.shape == img.shape[:2]
            data = b.reshape(w * h).astype(np.float32)
            f.write(data)


def gen_envi_raw(name, img: np.ndarray, dtype=np.float32, interleave="bsq", byteorder=0, header_offset=0,
                 extra: str = ""):
    """Write an ENVI file with a minimal header, for testing the different formats. The image is
    a (h,w,bands) array which is converted to dtype and written with the given interleave, byte
    order (0=little, 1=big) and number of junk bytes before the data. Extra is added to the header."""
    h, w, bands = img.shape
    codes = {np.uint8: 1, np.int16: 2, np.int32: 3, np.float32: 4, np.float64: 5,
             np.uint16: 12, np.uint32: 13, np.int64: 14, np.uint64: 15}
    with open(f"{name}.hdr", "w") as f:
        f.write(f"ENVI\nsamples = {w}\nlines = {h}\nbands = {bands}\ndata type = {codes[dtype]}\n")
        f.write(f"interleave = {interleave}\nbyte order = {byteorder}\nheader offset = {header_offset}\n")
        f.write(extra)

    if interleave == "bsq":
        data = img.transpose(2, 0, 1)
    elif interleave == "bil":
        data = img.transpose(0, 2, 1)
    else:
        data = img
    data = np.ascontiguousarray(data).astype(np.dtype(dtype).newbyteorder('<' if byteorder == 0 else '>'))
    with open(f"{name}.dat", "wb") as f:
        f.write(b"\xff" * header_offset)
        f.write(data.tobytes())
