from pathlib import Path

from pcot.subcommands import subcommand, argument
from pcot.utils import archive

"""
Code for creating reflectance data files
"""


@subcommand([
    argument('input', type=str, metavar='YAML_FILENAME', help="Input YAML file describing reflectance data"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename"),
],
    shortdesc="Process a YAML reflectance file and associated data into a PARC file")
def genrefl(args):
    import pcot
    from pcot.cameras import reflectances
    import yaml

    pcot.setup()

    out = reflectances.Reflectance()        # this is what we're building!
    with open(args.input) as f:
        # load the YAML file. Produces a dict, of course.
        d = yaml.safe_load(f)
        # Get the style of data we have - it's the same for all patches.
        patch_format = d['format']
        # now get the patches - the keys of this dict are patch names, the values depend on the format.
        patches = d['patches']
        for patch,val in patches.items():
            if patch_format == 'jack':
                print(f"Jack format: processing patch {patch} from directory {val}")
                out.load_jack(patch, Path(val))
            else:
                raise Exception(f"Patch format {patch_format} unknown")

    # serialise the resulting reflectance object
    t = out.serialise()

    with archive.FileArchive(args.output, "w") as a:
        a.writeJson("data", t)


