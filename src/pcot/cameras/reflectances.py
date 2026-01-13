"""
This file handles reflectance spectra for calibration targets, in particular the PCT.
We're using scipy's RegularGridInterpolator to handle the actual work.

Reflectance data itself is only loaded on demand when any kind of data query is made, so
having this loaded in startup isn't a problem.

"""
# See Notes on PCT Reflectance data in Obsidian

from scipy.interpolate import RegularGridInterpolator
from pathlib import Path
from typing import Dict, Optional, Any, List, Set, Tuple

import numpy as np
import logging

from pcot.cameras.filters import Filter
from pcot.utils import archive


logger = logging.getLogger(__name__)

class Reflectance:
    """
    Base for reflectances - both full reflectance measurements and angle-free data
    (angles passed to get_reflectances will be ignored in that case).
    """

    # this starts out as null, but when we load data from an archive the archive
    # metadata is stored here so we can show it.

    metadata: 'Metadata'    # copied from the FileArchive from which it is loaded
    path: Optional[Path]    # file path
    typename: str           # what kind of reflectance data? Used for debugging/listing only.
    patches: List[str]      # list of patches

    # this is how the interpolators will handle out of bounds angles and wavelengths.
    # We're specifying that we will always extrapolate from the gradient of the nearest
    # in-bounds values.
    BOUNDS_MODE = {'bounds_error':False, 'fill_value':None}


    def __init__(self, typename, metadata, interpolators=None, dimensions=100, path=None, patches=None):
        """
        Set up a reflectance spectrum object, either from interpolators passed in or get
        ready to load from a path. If a path is given we load lazily when the interpolation
        is done.

        * typename - type of the object as a string, for debugging and output
        * metadata - metadata from the file archive from which we are loaded
        * interpolators - dict of interpolator objects or None if we are going to load lazily
        * dimensions - dimensionality of the reflectance spectrum (e.g. 1 for a simple by-wavelength,
          3 if it's theta,phi,wavelength
        * path - path of the archive file
        * patches - list of patches to use if no interpolators are given

        Dimensions is the number of dimensions for each interpolator (which must match; _check_interpolators
        checks this).

        The object is a bunch of RegularGridInterpolator objects, one for each patch.
        """

        if interpolators is None:
            if patches is not None:
                self.patches = patches
            else:
                self.patches = []
        else:
            self.patches = sorted(interpolators.keys())

        self.patches = patches
        self.typename = typename
        self.metadata = metadata
        self.path = path
        self._interpolators = interpolators or {}
        # this will be large (100) if dimensions aren't specified, which typically happens when loading legacy data
        self._dimensions = dimensions

    def set_interpolators(self, interpolators):
        """Set all the interpolators at once and check them"""
        self._interpolators = interpolators
        self.patches = sorted(self._interpolators.keys())
        self._check_interpolators()

    def set_interpolator(self, patch, interpolator):
        """Set a single interpolator for a patch"""
        self._interpolators[patch] = interpolator
        self.patches = sorted(self._interpolators.keys())
        # may as well check them all
        self._check_interpolators()

    def serialise(self):
        """Used to serialise all kinds of Reflectance; the loader will check the
        number of dimensions to see what kind of reflectance data this is"""
        refls = {}
        for k,rgi in self._interpolators.items():
            refls[k] = {
                "points": rgi.grid,
                "values": rgi.values,
                "method": rgi.method,
            }
        out = {"dims": self._dimensions, "refls": refls}
        return out
        
    def get_patches(self):
        """returns all the patch names"""
        return self.patches

    def _get_interp(self, patch):
        """Get the interpolator for a patch or raise an exception"""
        self._load_interpolators()
        try:
            return self._interpolators[patch]
        except KeyError:
            raise KeyError(f"patch {patch} not in reflectance data")

    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        pass

    def get_reflectances(self, patch, phi, theta) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength
        """
        pass

    def get_reflectance(self, patch, phi, theta, wavelength) -> np.float32:
        """
        Return the reflectance at a single wavelength
        """
        pass

    def get_known_reflectance_for_filter(self, f: Filter, patch, phi, theta):
        """
        This will multiply the reflectance at each known wavelength with the filter's transmission at
        that wavelength, and total the result to give a total reflectance.
        """
        # get wavelengths for this patch and the reflectances
        wvls, refls = self.get_reflectances(patch, phi, theta)
        # get the filter response from the filters for these wavelengths, interpolating if required
        resp = f.getResponse(wvls)
        # do the multiplication and adds
        r = refls @ resp
        # and divide by the sum of the responses - refls says how much light is reflected, resp tells you
        # how much light gets through the filter at each wavelength. So the product at each wavelength
        # is the effective reflected light at that wavelength after the filter. The sum will be the total
        # reflected flux through the filter, but we need to divide by the amount of light which would pass
        # through if the patch were perfectly reflective. So we divide by the sum of the filter responses.
        return r / np.sum(resp)


    def _load_interpolators(self):
        """
        Interpolators are loaded on demand by the superclass
        """
        if len(self._interpolators) == 0:
            # only if we haven't loaded them already (or set them another way)
            dims = None
            interps = {}
            with archive.FileArchive(self.path) as a:
                metadata = a.metadata
                logging.debug(f"Loading {metadata.name} from {self.path}")
                # the format of the data can be found in the serialiser here and in genrefl code.
                json = a.readJson("data") # "data" is the name of the file
                for k, d in json["data"]["refls"].items():  # which contains a dict called "data", containing refls and dims.
                    rgi = RegularGridInterpolator(
                        d["points"],
                        d["values"],
                        method=d["method"],
                        **Reflectance.BOUNDS_MODE)
                    interps[k] = rgi
                    if dims is None:
                        dims = len(rgi.values.shape)
                    elif dims != len(rgi.values.shape):
                        raise Exception(f"Some patch interpolators have different dimensions in {self.path}")
                    elif dims != self._dimensions:
                        raise Exception(f"Some patch interpolators have incorrect for {self.__class__.__name__} dimensions in {self.path}")
                    interps[k] = rgi
                self.set_interpolators(interps)

        
    def _check_interpolators(self):
        """check the interpolators are valid for this reflectance"""
        assert isinstance(self._interpolators,dict)
        for v in self._interpolators.values():
            assert isinstance(v,RegularGridInterpolator)
            assert len(v.values.shape)==self._dimensions

        

class SimpleReflectance(Reflectance):
    """This is reflectance data without any angular information: just wavelengths and
    reflectances for each patch."""
    
    def __init__(self, interpolators=None, metadata=None, path=None, patches=None):
        super().__init__("Simple reflectance", metadata, interpolators, 1, path, patches)

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
                self.set_interpolator(k,i)

        
    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        self._load_interpolators() # ensure interpolators are loaded
        g = self._interpolators[patch].grid[0] # only one dimension here
        # so the angles will have a (0,0) range
        return [(0,0), (0,0), (np.min(g),np.max(g))]

    def get_reflectance(self, patch, phi, theta, wavelength):
        """
        Get reflectance at a single wavelength
        """
        # looks a bit weird. The call to _get_interp returns an interpolator, and we "call" that with the wavelengths.
        # Then we get the first value that comes out of the 1-element array returned.
        v = self._get_interp(patch)([wavelength, ])[0]
        return np.clip(v,0,None)

    def get_reflectances(self, patch, phi, theta, wavelengths=None):
        """
        Returns wavelengths and reflectances as np arrays
        """
        interp = self._get_interp(patch)
        if wavelengths is None:
            wvls = interp.grid[-1] # last axis in grid is the wavelength list
            refl = interp(wvls)
            refl = np.clip(refl,0,None)
            return wvls,refl
        else:
            return interp(wavelengths)




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

    def __init__(self, interpolators=None, metadata=None, path=None, patches=None):
        """Initialise from interpolators, or create empty dict"""
        super().__init__("BRDF for PCT", metadata, interpolators, 3, path, patches)


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

    def _get_interp(self,patch: str):
        self._load_interpolators()
        if not patch in self._interpolators:
            # this is a hack in case someone uses the weird Jack/Giselle names
            # and won't work on a non-PCT
            if not patch in PCTReflectance.rev_name_map:
                raise KeyError(f"patch {patch} not in reflectance data")
            patch = PCTReflectance.rev_name_map[patch]
        return super()._get_interp(patch)

    def get_range(self, patch:str):
        """returns the ranges of each axis (phi,theta,wvls) as tuples of (min,max)"""
        interp = self._get_interp(patch)
        return [(np.min(x),np.max(x)) for x in interp.grid]

    @staticmethod
    def _preprocess_angles(phi, theta):
        # we've only recorded half the phi values, and it's a weird
        # half. And we leave the possibility of changing theta if we need to
        while phi < 0:
            phi += 360

        if phi < 180:
            phi = -phi

        phi %= 360
        return phi, theta

        
    def get_reflectances(self, patch, phi, theta, wavelengths=None):
        """
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength.
        """

        phi, theta = PCTReflectance._preprocess_angles(phi, theta)
        interp = self._get_interp(patch)
        if wavelengths is None:
            wvls = interp.grid[-1] # last axis in grid is the wavelength list
            # we want to get the value for a known phi and theta that are the same for all values
            # so we fill a couple of rows with that data. We then fill the third row with the wavelengths,
            # and interpolate.
            input = np.column_stack((
                np.full(wvls.shape, phi),
                np.full(wvls.shape, theta),
                wvls))
            refl = interp(input)
            refl = np.clip(refl,0,None)  # clip to zero
            return wvls,refl
        else:
            return interp((phi, theta, wavelengths))


    def get_reflectance(self, patch, phi, theta, wavelength):
        phi, theta = PCTReflectance._preprocess_angles(phi, theta)
        interp = self._get_interp(patch)
        r = interp((phi,theta,wavelength))
        return np.clip(r, 0, None)

def load(file: Path):
    """Will create the appropriate kind of reflectance object. The actual data will be loaded
    the first time get_reflectances is called."""

    with archive.FileArchive(file,"r") as a:
        metadata = a.metadata
        logging.debug(f"Loading {metadata.name} from {file}")
        json = a.readJson("data",load_arrays=False)

    # given the number of dimensions, create and return the appropriate reflectance object
    data = json["data"] # get the data; it's saved under this key in genrefls
    dims = data["dims"]
    patches = data["refls"].keys()
    if dims == 1:   # just wavelength
        return SimpleReflectance(metadata=metadata,path=file,patches=patches)
    elif dims == 3: # wavelength and stereo angle
        return PCTReflectance(metadata=metadata,path=file, patches=patches)
    else:
        raise Exception(f"Bad number of dimensions for reflection interpolators in {file}: {dims}")
        

def test():
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
            v = d.get_reflectances("NG11", phi, theta, 600)
            vals_interpolated.append(v)
        ax.plot(thetas, vals_interpolated, marker="x")

    legend = ax.legend(loc="lower right",
                       labels=[f"phi={x}" for x in phis])

    plt.savefig("out.png")
    plt.show()

if __name__ == "__main__":
    test()

