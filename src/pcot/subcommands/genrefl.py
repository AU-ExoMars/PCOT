from pathlib import Path
import yaml
import logging

import pcot
from pcot.cameras import reflectances
from pcot.subcommands import subcommand, argument
from pcot.utils import archive

logger = logging.getLogger(__name__)


"""
Code for creating reflectance data files
"""

def load_jack_format(d:dict):
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
    out = reflectances.Reflectance()        # this is what we're building!
    patches = d['patches']
    for patch, val in patches.items():
        print(f"Jack format: processing patch {patch} from directory {val}")
        out.load_jack(patch, Path(val))
    return out


def load_simple_format(d:dict):
    """
    Load data in the "old" format. Here, the reflectances are in a single CSV
    file. Column headers: patch,wavelength,mean,sd
    I may well ignore sd...
    """
    file = d['file']
    out = reflectances.SimpleReflectance()
    out.load_simple_csv(Path(file))
    return out


@subcommand([
    argument('input', type=str, metavar='YAML_FILENAME', help="Input YAML file describing reflectance data"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename"),
],
    shortdesc="Process a YAML reflectance file and associated data into a PARC file")
def genrefl(args):
    pcot.setup()

    with open(args.input) as f:
        # load the YAML file. Produces a dict, of course.
        d = yaml.safe_load(f)

        # get basic metadata fields
        t = {k:d[k] for k in ('description','author','date','name','short')}
        # turn the date into a string
        t["date"] = t["date"].strftime("%Y-%m-%d")        

        # Get the style of data we have - it's the same for all patches.
        patch_format = d['format']
        if patch_format == 'jack':
            out = load_jack_format(d)
        elif patch_format == 'simple':
            
            out = load_simple_format(d)
        else:
            raise Exception(f"Patch format {patch_format} unknown")

    # serialise the resulting reflectance object into the dict we already have
    t["refls"]=out.serialise()

    # get extra metadata that's in the dict; there's some kinda duplication here because the author and
    # date stored in the metadata will be automatically generated from the system and won't be the values
    # stored in the YAML file. I think that might be a good idea - the metadata on the archive is about
    # the file, but the metadata in the data itself is about that data.
    meta = archive.Metadata(type=archive.ArchiveType.REFLDATA,
                            description=t['description'],
                            short=t['short'])

    logger.info(f"Metadata:\n{meta}")

    # and write to an archive
    with archive.FileArchive(args.output, "w",metadata=meta) as a:
        a.writeJson("data", t)


