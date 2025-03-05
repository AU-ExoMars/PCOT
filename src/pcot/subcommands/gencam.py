#!/usr/bin/env python3
from pcot.subcommands import subcommand, argument

@subcommand([
    argument('params',type=str,metavar='YAML_FILENAME',help="Input YAML file with parameters"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename")
    ],
    shortdesc="Process a YAML camera file into a PARC file")
def gencam(args):
    """
    Given camera data in the current directory, create a .parc file from that data for use as camera parameter data.
    The file format is documented in the PCOT documentation, but is essentially a YAML file with a specific structure.
    """
    with open(args.params) as f:
        from pcot.cameras import camdata
        import yaml
        d = yaml.safe_load(f)

        fs = createFilters(d["filters"])
        p = camdata.CameraParams(fs)
        p.params.name = d["name"]
        p.params.date = d["date"].strftime("%Y-%m-%d")
        p.params.author = d["author"]
        p.params.description = d["description"]
        p.params.short = d["short"]
        store = camdata.CameraData.openStoreAndWrite(args.output, p)

        # add more data here

        store.close()


def createFilters(filter_dicts):
    from pcot.cameras import filters
    fs = {}
    for k, d in filter_dicts.items():
        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d.get("transmission", 1.0),
            name=k,
            position=d.get("position", k))
        fs[k] = f
    return fs


