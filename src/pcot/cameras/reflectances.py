"""
This file handles reflectance spectra for calibration targets, in particular the PCT.
We're using scipy's RegularGridInterpolator to handle the 
"""
# See Notes on PCT Reflectance data in Obsidian

from scipy.interpolate import RegularGridInterpolator
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import logging

from pcot.utils import archive


logger = logging.getLogger(__name__)

class Reflectance:
    """
    Base for reflectances - both full reflectance measurements and angle-free data
    (angles passed to get_reflectances will be ignored in that case).
    """

    # this starts out as null, but when we load data from an archive the archive
    # metadata is stored here so we can show it.

    metadata: 'Metadata'
    path: Optional[Path]
    typename: str

    # this is how the interpolators will handle out of bounds angles and wavelengths.
    # We're specifying that we will always extrapolate from the gradient of the nearest
    # in-bounds values.
    BOUNDS_MODE = {'bounds_error':False, 'fill_value':None}


    def __init__(self, typename, metadata, interpolators, expected_dims, path=None):
        self.typename = typename
        self.metadata = metadata
        self._interpolators = {} if interpolators is None else interpolators
        # if interpolators were provided check they have the right dimensions
        self._check_interpolators(expected_dims)
        self.path = path

    def serialise(self):
        """Used to serialise all kinds of Reflectance; the loader will check the
        number of dimensions to see what kind of reflectance data this is"""
        out = {}
        for k,rgi in self._interpolators.items():
            out[k] = {
                "points": rgi.grid,
                "values": rgi.values,
                "method": rgi.method,
            }
        return out
        
    def get_patches(self):
        """returns all the patch names"""
        return self._interpolators.keys()
    
        
    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        pass
        
    def get_reflectances(self, patch, phi, theta, wavelength=None):
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength
        """
        pass
        
    def _check_interpolators(self, expected_dims:int):
        """In constructors, check the interpolators are valid for this reflectance"""
        assert isinstance(self._interpolators,dict)
        for v in self._interpolators.values():
            assert isinstance(v,RegularGridInterpolator)
            assert len(v.values.shape)==expected_dims
        

class SimpleReflectance(Reflectance):
    """This is reflectance data without any angular information: just wavelengths and
    reflectances for each patch."""
    
    def __init__(self, interpolators=None, metadata=None, path=None):
        """Initialise from interpolators, or create empty dict"""
        super().__init__("Simple reflectance", metadata, interpolators, 1, path)

    def load_simple_csv(self,csv:Path):
        """Load data from a CSV file with the columns patch,wavelength,mean,sd"""
        with open(csv) as f:
            import csv
            reader = csv.DictReader(f)
            # read the data into a dict of patches, each of which has a
            # dict of three lists: wvls, means, and sds
            data = {}
            for row in reader:
                patch = row['patch']
                wvl = row['wavelength']
                mean = row['mean']
                sd = row['sd']
                if patch not in data:
                    # we ignore SD for now
                    data[patch]={'wvls':[], 'means':[], 'sds':[]}
                data[patch]['wvls'].append(wvl)
                data[patch]['means'].append(mean)
                data[patch]['sds'].append(sd)
            # convert the lists into arrays and create a regular grid interpolator for each.
            # We're ignoring stddev for now.
            for k,v in data.items():
                x = np.array(v['wvls'],np.float32)
                y = np.array(v['means'],np.float32)
                i = RegularGridInterpolator((x,),y, **Reflectance.BOUNDS_MODE)
                self._interpolators[k]=i
        
        
    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        g = self._interpolators[patch].grid[0] # only one dimension here
        # so the angles will have a (0,0) range
        return [(0,0), (0,0), (np.min(g),np.max(g))]
        
    def get_reflectances(self, patch, phi, theta, wavelength=None):
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength
        """
        if not patch in self._interpolators:
            raise Exception(f"patch {patch} not in reflectance data")
        interp = self._interpolators[patch]
        if wavelength is None:
            wvls = interp.grid[-1] # last axis in grid is the wavelength list
            refl = interp(wvls)
            return wvls,refl
        else:
            return interp([wavelength,])[0] # ugly
        



class PCTReflectance(Reflectance):
    """
    Reflectance data with a single stereo angle, and is assumed to be generated
    from Jack Langston's measurements for the PCT. The phi angles measured are between 210-360 (0),
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

    def __init__(self, interpolators=None, metadata=None, path=None):
        """Initialise from interpolators, or create empty dict"""
        super().__init__("BRDF for PCT", metadata, interpolators, 3, path)


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
            t,w,d = PCTReflectance._load_jack_data_for_phi(path, i)
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
        self._interpolators[patch] = RegularGridInterpolator(points,data, **Reflectance.BOUNDS_MODE)
        
        
    def get_interpolator(self,patch: str):
        return self._interpolators[patch]
        
    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        interp = self._interpolators[patch]
        return [(np.min(x),np.max(x)) for x in interp.grid]
        
    def get_reflectances(self, patch, phi, theta, wavelength=None):
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength.
        """
        if not patch in self._interpolators:
            # this is a hack in case someone uses the weird Jack/Giselle names
            # and won't work on a non-PCT
            if not patch in PCTReflectance.rev_name_map:
                raise KeyError(f"patch {patch} not in reflectance data")
            patch = PCTReflectance.rev_name_map[patch]
        
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
            

def load(file: Path):
    """Will deserialise the interpolators and create the appropriate reflectance object"""

    # load and create all the interpolators, making sure to record the number of dimensions
    # and ensure they are the same for all.
    dims = None
    interps = {}
    with archive.FileArchive(file,"r") as a:
        metadata = a.metadata
        logging.debug(f"Loading {metadata.name} from {file}")
        json = a.readJson("data")
        for k, d in json["refls"].items():
            rgi = RegularGridInterpolator(
                d["points"],
                d["values"],
                method=d["method"],
                **Reflectance.BOUNDS_MODE)
            interps[k] = rgi
            if dims is None:
                dims = len(rgi.values.shape)
            elif dims != len(rgi.values.shape):
                raise Exception(f"Some patch interpolators have different dimensions in {file}")
            interps[k] = rgi

    # given the number of dimensions, create and return the appropriate reflectance object
    if dims == 1:   # just wavelength
        return SimpleReflectance(interps, metadata=metadata,path=file)
    elif dims == 3: # wavelength and stereo angle
        return PCTReflectance(interps, metadata=metadata,path=file)
    else:
        raise Exception(f"Bad number of dimensions for reflection interpolators in {file}: {dims}")
        


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    logging.debug("Loading")
    d = load(Path("pct.parc"))
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



