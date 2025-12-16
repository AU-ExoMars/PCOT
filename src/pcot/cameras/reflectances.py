"""
This file handles reflectance spectra for calibration targets, in particular the PCT.
We're using scipy's RegularGridInterpolator to handle the 
"""

# See Notes on PCT Reflectance data in Obsidian

from scipy.interpolate import RegularGridInterpolator
from pathlib import Path
from typing import Dict

import numpy as np
import logging

from pcot.utils import archive


logger = logging.getLogger(__name__)


class Reflectance:
    """
    Reflectance data, from Jack Langston's measurements. The phi angles measured are between 210-360 (0),
    and the theta goes from -80 to 80. Incident is at 24 degrees; we assume that the PCT is around this angle
    from the camera. Load the data with deserialise() from a FileArchive, then use get_reflectances to get
    the wavelengths at a particular pair of angles for a particular patch.

    NOTE THAT CURRENTLY THETA VALUES BETWEEN 20 AND 40 ARE WRONG due to limitations of the measurement hardware.
    """
    name_map = {  # maps our names onto Jack's names
        "NG4": "black",
        "Pyroceram": "white",
        "WCT2065": "brown",
        "BG18": "green",
        "NG11": "grey",
        "RG610": "red",
        "BG3": "blue",
        "OG515": "yellow"
    }
    # in case someone (Jack) asks for the name in the data.
    rev_name_map = {v: k for k, v in name_map.items()}

    # this is the thing that we get data from!
    _interpolators: Dict[str,RegularGridInterpolator]

    def __init__(self, file: Path = None):
        """If a path is present, will load data in our format. Otherwise data
        can be loaded from a set of text files as given by Jack Langston's data, Sept 2025.
        Or from just a list of stuff.
        You need a YAML file to say what's what, though."""
        
        self._interpolators = {} # no interpolators!

        if file:
            """
            Deserialise from a FileArchive - this is how you load the data. Don't use load_jack, that's for
            converting from Jack's measurements.
            """

            with archive.FileArchive(file,"r") as a:
                logging.debug("Loading")
                json = a.readJson("data")
                for k, d in json.items():
                    rgi = RegularGridInterpolator(
                        d["points"],
                        d["values"],
                        method=d["method"],
                        bounds_error=False,
                        fill_value=0)
                    self._interpolators[k] = rgi

    def serialise(self):
        """
        Serialise to JSON/numpy arrays, such that we can save the result in a FileArchive.
        """
        out = {}
        for k,rgi in self._interpolators.items():
            out[k] = {
                "points": rgi.grid,
                "values": rgi.values,
                "method": rgi.method,
            }
        return out

        
    @staticmethod
    def _load_jack_data_for_phi(p: Path, phi):
        """Load the data for a single phi angle in a single patch directory in Jack's format.
        The data is assumed to be in a set of files called <path>/Phi_<phi>/<patch>_<scan>.sed,
        as captured by an RS-3500, where <scan> is a scan number; scan*5-80 gives theta.
        
        The output is a triple of two lists an a 2D array:
            theta values
            wavelengths
            data points indexed by (theta,wavelength)
            
        Upstream we'll need to check that the thetas and wavelengths are all the same for all data in the patch.
        """

        # we have recorded the phi angles 210-330, and zero, leaving half the
        # angles out in the assumption that the reflection is valid (e.g.
        # phi=210 will give the same results as phi=30).
        # We'll store the zero angle as 180 so we end up with the range
        # 180-330, rather than 210-360. Makes it easier later.
        if phi == 180:
            phi = 0

        p = p / f"Phi_{phi:02}"

        thetas = []
        refldata_by_theta = []
        
        wvls = None       # all wavelengths must be the same

        if not p.exists():
            return None

        for x in p.glob("*.sed"):
            # extract scan number
            _, scan = x.stem.split("_")

            # scans are numbered 1 to 33, and are for theta
            # values from -80 to 80. See the readme.
            
            scan = int(scan)-1    # scans start at 1.
            theta = scan * 5 - 80
            
            if theta<-80 or theta>80:
                continue # ignore weird extra data!
            if theta==-80 or theta==80:
                print(f"{x}: {theta}")
            with open(x) as f:
                wvls_for_theta = []
                refls = []

                mode = 'waitchans'
                while line := f.readline():
                    line = line.strip()
                    if mode == 'waitchans':
                        if 'Channels' in line:
                            _, chans = line.split(':')
                            chans = int(chans)
                            mode = 'waitdata'
                    elif mode == 'waitdata':
                        if line.startswith('Wvl'):
                            mode = 'data'
                    else:
                        line = line.split()
                        w = float(line[0])
                        r = float(line[3]) / 100.0  # raw data is percentage
                        wvls_for_theta.append(w)
                        refls.append(r)

                assert len(wvls_for_theta) == chans
                assert len(refls) == chans
                
                if wvls is None:
                    wvls = wvls_for_theta
                elif wvls != wvls_for_theta:
                    raise Exception(f"Wavelength disparity for file {f}")

            thetas.append(theta)
            
            refl_data = np.array(refls, np.float32)
            refldata_by_theta.append(refl_data)
            
        # sort by theta. This is a clever hack because sort sorts lexicographically,
        # and zip creates tuples. So it will always sort by the first item.
        t = sorted(zip(thetas,refldata_by_theta))
        thetas, refldata_by_theta = zip(*t)

        return (thetas, wvls, np.array(refldata_by_theta))

    def load_jack(self, patch: str, path: Path):
        phis = []
        thetas = None
        wvls = None
        data = []
        # try to load each possible phi angle's data
        for i in [180, 210, 240, 270, 300, 330]:
            t,w,d = Reflectance._load_jack_data_for_phi(path, i)
            # and make sure all the thetas and wavelengths are
            # the same!
            if thetas is None:
                thetas = t
            elif thetas != t:
                raise Exception(f"Thetas mismatch for path {path}")
            if wvls is None:
                wvls = w
            elif wvls != w:
                raise Exception(f"Wavelengths mismatch for path {path}")
                
            phis.append(i)
            data.append(d)
            
        # create the big array and points data
        data = np.stack(data,axis=0)
        points = [np.array(x,np.float32) for x in (phis,thetas,wvls)]
        # and the interpolator
        self._interpolators[patch] = RegularGridInterpolator(points,data,bounds_error=False,fill_value=0)
        
        
    def get_interpolator(self,patch: str):
        return self._interpolators[patch]
        
    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        interp = self._interpolators[patch]
        return [(np.min(x),np.max(x)) for x in interp.grid]
        
    def get_reflectances(self, patch, phi, theta, wavelength=None):
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength
        """
        if not patch in self._interpolators:
            if not patch in Reflectance.rev_name_map:
                raise Exception(f"patch {patch} not in reflectance data")
            patch = Reflectance.rev_name_map[patch]
        
        # we've only recorded half the phi values, and it's a weird
        # half
        while phi < 0:
            phi += 360

        if phi < 180:
            phi = -phi

        phi %= 360

        interp = self._interpolators[patch]
        if wavelength is None:
            wvls = interp.grid[-1] # last axis in grid is the wavelength list
            input = np.column_stack((
                np.full(wvls.shape, phi),
                np.full(wvls.shape, theta),
                wvls))
            refl = interp(input)
            return wvls,refl
        else:
            return interp((phi,theta,wavelength))
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    if False:
        # read Jack's data and convert
        d = Reflectance()
        d.load(Path("."))
        t = d.serialise()

        with archive.FileArchive("pctrefls.parc", "w") as a:
            a.writeJson("data", t)

    with archive.FileArchive("pctrefls.parc", "r") as a:
        logging.debug("Loading")
        t = a.readJson("data")
        d = Reflectance(t)
        logging.debug("Loaded")

        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.set_xlabel("theta")
        ax.set_ylabel("reflectance")

        # plot the reflectance at a certain wavelength for different
        # thetas at a given phi (requires interpolation)
        thetas = np.arange(-75, 65)
        phis = np.arange(0, 180, 30)
        for phi in phis:
            vals_interpolated = []
            for theta in thetas:
                v = d.get_reflectances("NG11", phi, theta, wavelength=600)
                vals_interpolated.append(v)
            ax.plot(thetas, vals_interpolated, marker="x")

        legend = ax.legend(loc="lower right",
                           labels=[f"phi={x}" for x in phis])

        plt.savefig("out.png")
        plt.show()



