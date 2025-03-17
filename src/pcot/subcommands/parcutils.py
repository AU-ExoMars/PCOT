from pcot.subcommands import subcommand,argument

@subcommand(
    [argument("filename", metavar="FILENAME", help="Name of the PARC file to list")],
    shortdesc="List the contents of a PARC file"
)
def lsparc(args):
    """
    List the contents of a PARC file.
    """
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    import datetime

    a = FileArchive(args.filename)
    ds = DatumStore(a)
    manifest = ds.getManifest()
    for k in manifest:
        meta = manifest[k]
        created = meta.created.strftime("%Y-%m-%d")

        print(f"{k:>20} : {meta.datumtype:12} {created:11} {meta.description}")


@subcommand(
    [
        argument("filename", metavar="FILENAME", help="Name of the PARC file"),
        argument("itemname", metavar="ITEMNAME", help="Name of the item")
    ],
    shortdesc="Print a Datum stored in a PARC to stdout"
)
def viewparc(args):
    """
    Output the text representation of a Datum stored in a PARC to stdout.
    """
    import pcot
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    import datetime

    pcot.setup() # need this to get datum types setup
    a = FileArchive(args.filename)
    ds = DatumStore(a)
    
    d = ds.get(args.itemname)
    print(d.tp.view(d))
