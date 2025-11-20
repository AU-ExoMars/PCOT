from pathlib import Path
import yaml

import pcot
from pcot.cameras import reflectances
from pcot.subcommands import subcommand, argument
from pcot.utils import archive

"""
Code for creating reflectance data files
"""

def load_jack_format(out: reflectances.Reflectance, d:dict):
    """
    Load data for patches in Jack's format.
    out: the reflectance object into which we will load the data
    d: the yaml dict loaded from the file

    There should be a "patches" directory. The keys of this are the patch names, the values are data directory names.

    These have files in the form Phi_<angle>/<patchname>_<scannumber>.sed
        where
        -   <angle> is the phi angle 00,30,60,210,240,270,300,330 (note that 0=00 here!)
        -   <scannumber> maps to theta, such that theta=scan*5-80.
    Each sed file contains wavelength/reflectance for each patch at the given angles, as read by
    an RS-3500 spectroradiometer.
    (See reflectances.Reflectance.load_jack() etc. for more details)
    """
    patches = d['patches']
    for patch, val in patches.items():
        print(f"Jack format: processing patch {patch} from directory {val}")
        out.load_jack(patch, Path(val))


def load_simple_format(out: reflectances.Reflectance, d:dict):
    """
    Load data in the "old" format. Here, the reflectances are in a single CSV
    file. Column headers: patch,wavelength,mean,sd
    I may well ignore sd...
    """


@subcommand([
    argument('input', type=str, metavar='YAML_FILENAME', help="Input YAML file describing reflectance data"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename"),
],
    shortdesc="Process a YAML reflectance file and associated data into a PARC file")
def genrefl(args):
    pcot.setup()

    out = reflectances.Reflectance()        # this is what we're building!
    with open(args.input) as f:
        # load the YAML file. Produces a dict, of course.
        d = yaml.safe_load(f)
        # Get the style of data we have - it's the same for all patches.
        patch_format = d['format']
        if patch_format == 'jack':
            load_jack_format(out, d)
        elif patch_format == 'simple':
            load_simple_format(out, d)
        else:
            raise Exception(f"Patch format {patch_format} unknown")

    # serialise the resulting reflectance object
    t = out.serialise()

    with archive.FileArchive(args.output, "w") as a:
        a.writeJson("data", t)


