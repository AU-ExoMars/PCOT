"""
This file handles reflectance spectra for calibration targets, in particular the PCT.
This is typically in the form of a SortedInterpolatedDict for each patch.
"""

# See Notes on PCT Reflectance data in Obsidian

from pathlib import Path
import numpy as np
import logging

from pcot.utils.sortedinterpdict import SortedInterpolatedDict

logger = logging.getLogger(__name__)


class PCTReflectance:
    """
    PCT reflectance data, from Jack Langston's measurements. The phi angles measured are between 210-360 (0),
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

    def __init__(self, file: Path = None):
        """If a path is present, will load data in our format. Otherwise data
        can be loaded from a set of text files as given by Jack Langston's data, Sept 2025"""

        # this data will be a dict of patch name (e.g. "NG4") to
        # SortedInterpolatedDicts of phi to SortedInterpolatedDicts of theta to
        # (wavelength,reflectance) tuples where wavelength and
        # reflectance are 1D numpy arrays.
        #
        # A SortedInterpolatedDict keeps keys in order so that we can get
        # the data around a given value.

        self._data = None

        if file:
            raise Exception("Not yet implemented")

    def serialise(self):
        """
        Serialise to JSON/numpy arrays, such that we can save the result in a FileArchive.
        """
        out = {}
        for k, v in self._data.items():
            # each value is a SID of SIDs. This will serialise
            # the outer layer, but the inner will need doing.
            t = v.serialise()
            # and this will serialise the inner SIDs
            t["values"] = [x.serialise() for x in t["values"]]
            out[k] = t
        return out

    @staticmethod
    def deserialise(d):
        """
        Deserialise from a FileArchive - this is how you load the data. Don't use load_jack, that's for
        converting from Jack's measurements.
        ```
        with archive.FileArchive("pctrefls.parc","r") as a:
            logging.debug("Loading")
            t = a.readJson("data")
            d = PCTReflectance().deserialise(t)
            logging.debug("Loaded")
        ```

        """
        outd = {}
        for k, v in d.items():
            # we deserialise the outer layer
            t = SortedInterpolatedDict.deserialise(v)
            # and now the inner values
            for k2, v2 in t.dict.items():
                t.dict[k2] = SortedInterpolatedDict.deserialise(v2)
            outd[k] = t
        out = PCTReflectance()
        out._data = outd
        return out

    @staticmethod
    def _load_jack_data_for_phi(p: Path, phi):
        """Load the data for a single phi angle in a single patch directory in Jack's format.
        The data is assumed to be in a set of files called <path>/Phi_<phi>/<patch>_<scan>.sed,
        as captured by an RS-3500, where <scan> is a scan number; scan*5-80 gives theta.
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

        if not p.exists():
            return None

        for x in p.glob("*.sed"):
            # extract scan number
            _, scan = x.stem.split("_")
            theta = int(scan) * 5 - 80  # see readme

            with open(x) as f:
                wvls = []
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
                        wvls.append(w)
                        refls.append(r)

                assert len(wvls) == chans
                assert len(refls) == chans

            thetas.append(theta)
            # the actual reflectance data is a tuple of two np arrays - one with the wavelengths,
            # the other with the reflectances at those wavelengths
            refl_data = (np.array(wvls, dtype=np.float32), np.array(refls, np.float32))
            refldata_by_theta.append(refl_data)
        return SortedInterpolatedDict(thetas, refldata_by_theta)

    @staticmethod
    def _load_jack_data_for_patch(p: Path):
        """Load all the data for a given patch in Jack's format (see above)"""
        phis = []
        vals = []
        logger.info(f"Loading patch from {p}")
        for i in [180, 210, 240, 270, 300, 330]:
            r = PCTReflectance._load_data_for_phi(p, i)
            if r:
                phis.append(i)
                vals.append(r)

        return SortedInterpolatedDict(phis, vals, period=360)

    def load_jack(self, dir: Path):
        """Loads all the data from Jack's measurements. Really you'll want to use
        the serialise/deserialise with an archive.
        These are in the form <patchname>/Phi_<angle>/<patchname>_<scannumber>.sed
        where
        -   <patchname> is the "Jack/Giselle" patch name (green,brown etc..)
        -   <angle> is the phi angle 00,30,60,210,240,270,300,330 (note that 0=00 here!)
        -   <scannumber> maps to theta, such that theta=scan*5-80.
        """

        name_map = PCTReflectance.name_map
        #        name_map = {"NG11":"grey"}           # DEBUGGING, just process one!

        self._data = {}
        for k, v in name_map.items():
            path = dir / v
            self._data[k] = self._load_data_for_patch(path)

    def get_reflectances(self, patch, phi, theta, wavelength=None):
        """
        Get the 4 points around a given point in the (phi,theta) grid.
        We're going to rename phi as x, and theta as y, for brevity and
        so it's easier to think about.
        Returns wavelengths and reflectances as np arrays, unless wavelength is set
        in which case it will return the value at that wavelength
        """

        if not patch in self._data:
            if not patch in PCTReflectance.rev_name_map:
                raise Exception(f"patch {patch} not in reflectance data")
            patch = PCTReflectance.rev_name_map[patch]

        # we've only recorded half the phi values, and it's a weird
        # half
        while phi < 0:
            phi += 360

        if phi < 180:
            phi = -phi

        phi %= 360

        d = self._data[patch]

        # get the theta data for the high and low phi points.
        x1, x2 = d.around(phi)
        x1v, x2v = d[x1], d[x2]

        # get the prev, next theta data for those two points.
        y11, y12 = x1v.around(theta)
        y11v, y12v = x1v[y11], x1v[y12]
        y21, y22 = x2v.around(theta)
        y21v, y22v = x2v[y21], x2v[y22]

        # we now have four points.
        # turn those values into just the reflectances, but make sure the wavelengths are all the same
        w1, v11 = y11v
        w2, v12 = y12v
        w3, v21 = y21v
        w4, v22 = y22v

        assert np.array_equal(w1, w2)
        assert np.array_equal(w2, w3)
        assert np.array_equal(w3, w4)

        # the actual interpolation. We have a quad with coordinates
        # (x1, y11) value v11
        # (x2, y21) value v21
        # (x1, y12) value v12
        # (x2, y22) value v22

        # Map x to u in [0, 1]
        u = 0 if x1 == x2 else (phi - x1) / (x2 - x1)

        # Interpolate y positions for top and bottom edges at x
        y_bottom = (1 - u) * y11 + u * y21
        y_top = (1 - u) * y12 + u * y22

        # Map y to v in [0, 1]
        v = 0 if y_top == y_bottom else (theta - y_top) / (y_bottom - y_top)

        # interpolate between the two values at the bottom and top edges
        v_top = (1 - u) * v11 + u * v21
        v_bottom = (1 - u) * v12 + u * v22

        v_final = (1 - v) * v_bottom + v * v_top

        if wavelength:
            # believe it or not, this is quicker than np.where
            for k, v in enumerate(w1):
                if v == wavelength:
                    return v_final[k]
            raise ValueError(f"Wavelength {wavelength} not in data")

        else:
            return w1, v_final  # return wavelengths and reflectances


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    from pcot.utils import archive

    if False:
        # read Jack's data and convert
        d = PCTReflectance()
        d.load(Path("."))
        t = d.serialise()

        with archive.FileArchive("pctrefls.parc", "w") as a:
            a.writeJson("data", t)

    with archive.FileArchive("pctrefls.parc", "r") as a:
        logging.debug("Loading")
        t = a.readJson("data")
        d = PCTReflectance().deserialise(t)
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



