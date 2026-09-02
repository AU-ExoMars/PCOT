import sys

from PySide6 import QtWidgets
import click

from pcot.parameters.taggedaggregates import TaggedDict, TaggedList
from pcot.subcommands.subcommands import cli
from pcot.ui.taggedaggregates import AggregateEditorDialog


@cli.command(short_help="Get a value (or all values) from the config file.")
@click.argument("key", required=False)
def getconfig(key):
    """
    Get a value from the config file. If no key is given, all values are shown. Values will be shown as
    section.key = value (which isn't quite how they appear in the .ini file).
    """
    import pcot.config
    from pcot.parameters.taggedaggregates import TaggedDict,TaggedList

    def dump(value, prefix=""):
        if isinstance(value, TaggedDict):
            for k,v in value.items():
                path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (TaggedDict, TaggedList)):
                    dump(v, path)
                else:
                    print(f"{path} = {v}")
        if isinstance(value, TaggedList):
            for idx,v in enumerate(value.get()):
                path = f"{prefix}.{idx}" if prefix else idx
                if isinstance(v, (TaggedDict, TaggedList)):
                    dump(v, path)
                else:
                    print(f"{path} = {v}")

    if key is None:
        dump(pcot.config.data)
    else:
        # split the provided path into elements
        path = key.split(".")
        d = pcot.config.data
        while len(path) > 0:
            k = path[0]
            if k not in d:
                raise KeyError(f"Key '{key}' not found in config file")
            d = d[k]
            path = path[1:]
        if isinstance(d, TaggedDict or TaggedList):
            dump(d, key)
        else:
            print(d)


@cli.command(short_help="Set a value in the config file")
@click.argument("key")
@click.argument("value")
def setconfig(key, value):
    """
    Set a value in the config file. This is a simple key-value store for the application.
    You can also edit the config file directly - it will be called .pcot.ini in your home
    directory. The key is in the form section.key, where section is the section in the .ini file.
    If the section is Default, you can omit it. See "pcot getconfig -h" to see the current values.
    """
    import pcot.config

    keys = key.split(".")
    current = pcot.config.data
    v = value

    for i, k in enumerate(keys):
        is_last = (i == len(keys) - 1)

        if k not in current:
            raise KeyError(f"Key '{k}' not found at path: " f"{'.'.join(keys[:i]) or ''}")

        if is_last:
            print("SET")
            tp = current.tag(k).type
            if tp == float:
                v = float(v)
            elif tp == int:
                v = int(v)
            current[k] = v
            pcot.config.save()
            return

        # Not last: must be a dict
        if not isinstance(current[k], (TaggedDict, TaggedList)):
            raise KeyError("Item at "
                f"Item at '{'.'.join(keys[:i+1])}' is not a dict or list, "
                f"but a {type(current[k]).__name__}"
            )

        if isinstance(current[k], TaggedDict):
            current = current[k]
        elif isinstance(current[k], TaggedList):
            try:
                k = int(k)
            except:
                raise KeyError(f"Could not convert '{k}' to int at {'.'.join(keys[:i+1])}")
            current = current[k]


@cli.command(short_help="Run the configuration UI")
def config():
    import pcot.config
    app = QtWidgets.QApplication(sys.argv)

    dialog = AggregateEditorDialog(pcot.config.data)
    dialog.exec()
    if dialog.data():
        pcot.config.data = dialog.data()
        pcot.config.save()
        print("Saved")
    else:
        print("You rejected the changes")
