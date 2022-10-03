import pcot
import os
from PySide2 import QtWidgets
from PySide2.QtWidgets import QAction, QMessageBox


import numpy as np
from typing import List


def _genheader(f, w: int, h: int, freqs: List[float]):
    """Crude stuff for writing a basic ENVI file. Lots of assumptions made."""

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
    f.write("wavelength units = nm\ndata ignore value = 241.000000\n")
    f.write("default stretch = 0.000000000000e+000 1.000000000000e+000 linear\n")
    g = 1.0
    s = ", ".join([f"{g:.4e}" for f in freqs])
    f.write(f"data gain values = {{\n {s}}}\n")
    f.write("calibration target label = MacBeth_ColorChecker\n")
    f.write("camera name = LWAC\n")
    f.write("camera system = SIM\n")
    t = 0.01
    s = ", ".join([f"{t:0.2f}" for f in freqs])
    f.write(f"exposure times = {{\n {s}}}\n")
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


def test(w):
    """Function takes a PCOT main window. It finds the input 0 if it can,
    and then saves an ENVI from that image."""
    
    try:
        node = w.doc.getNodeByName("input 0")
    except NameError:
        print("cannot find node")
        return
        
    res = QtWidgets.QFileDialog.getSaveFileName(w,
                                                "ENVI file ",
                                                os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                "ENVI files (*.hdr)")
    if res[0] != '':
        (root, ext) = os.path.splitext(res[0])
        # get the output of that input 0 node
        img = node.getOutput(0,pcot.datum.Datum.IMG)

        # convert the sources to frequencies, assuming there is only
        # one source per channel and they all have centre wavelength values
        
        freqs = [next(iter(s)).getFilter().cwl for s in img.sources]
        
        # write the result file
        gen_envi(root, freqs, img.img)
        
        

def addMenus(w):
    """Add an item to the Edit menu"""
    act = QAction("wibble",parent=w)
    w.menuEdit.addAction(act)
    act.triggered.connect(lambda: test(w))
    

pcot.config.addMainWindowHook(addMenus)
