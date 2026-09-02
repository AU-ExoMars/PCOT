import click

from pcot.subcommands.subcommands import cli
from pcot.utils.table import Table


@cli.command(short_help="List the contents and metadata of a PARC file")
@click.argument("filename")
@click.option("--meta", is_flag=True, help="Only show the metadata")
@click.option("--nometa", is_flag=True, help="Do not show the metadata")
@click.option("--history", is_flag=True, help="Show the archive's history metadata")
def lsparc(filename, meta, nometa, history):
    """
    List the contents of a PARC datum store and its metadata.
    """
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    import datetime

    a = FileArchive(filename)

    if not nometa:
        if a.metadata.is_loaded():
            for k in ['name','type','author','date','pcotversion','short']:
                print(f"{k:20} {getattr(a.metadata,k)}")

            desc = a.metadata.description
            if desc!="":
                print("Description:")
                print(desc)

            if history:
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


    if not meta:
        # show contents as well as metadata
        print("Contents:")
        ds = DatumStore(a)
        manifest = ds.getManifest()
        if len(manifest)==0:
            print(f"No datum items found; archive type is {a.metadata.type}")
        for k in manifest:
            m = manifest[k]
            created = m.created.strftime("%Y-%m-%d")

            print(f"{k:>20} : {m.datumtype:12} {created:11} {m.description}")


@cli.command(short_help="Print a Datum stored in a PARC to stdout")
@click.argument("filename")
@click.argument("itemname")
def viewparc(filename, itemname):
    """
    Output the text representation of a Datum stored in a PARC to stdout.
    """
    import pcot
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    import datetime

    pcot.setup() # need this to get datum types setup
    a = FileArchive(filename)
    ds = DatumStore(a)

    d = ds.get(itemname)
    print(d.tp.view(d))
