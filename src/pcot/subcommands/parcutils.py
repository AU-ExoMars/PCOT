from pcot.subcommands import subcommand,argument
from pcot.utils.table import Table

@subcommand(
    [
        argument("filename", metavar="FILENAME", help="Name of the PARC file to list"),
        argument("--meta", help="Only show the metadata", action="store_true"),
        argument("--nometa", help="Do not show the metadata", action="store_true"),
        argument("--history", help="Show the archive's history metadata", action="store_true")
    ],
    shortdesc="List the contents and metadata of a PARC file"
)
def lsparc(args):
    """
    List the contents of a PARC datum store and its metadata
    """
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    import datetime

    a = FileArchive(args.filename)
    
    if not args.nometa:
        if a.metadata.is_loaded():
            for k in ['name','type','author','date','pcotversion','short']:
                print(f"{k:20} {getattr(a.metadata,k)}")

            desc = a.metadata.description
            if desc!="":
                print("Description:")
                print(desc)

            if args.history:
                t = Table()
                for e in a.metadata.history:
                    t.newRow()
                    t.add('date',e.get('date',''))
                    for k,v in e.items():
                        if k != 'date':
                            t.add(k,v)
                print("\n"+t.text("HISTORY"))
        else:
            print("No metadata (old archive?)")
        

    if not args.meta:
        # show contents as well as metadata
        print("Contents:")
        ds = DatumStore(a)
        manifest = ds.getManifest()
        if len(manifest)==0:
            print(f"No datum items found; archive type is {a.metadata.type}")
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
