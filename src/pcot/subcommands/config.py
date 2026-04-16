from pcot.parameters.taggedaggregates import TaggedDict, TaggedList
from pcot.subcommands import subcommand,argument

@subcommand([
    argument("key", metavar="KEY", help="Name of config item to get", nargs="?"),
    ],
    shortdesc="Get a value (or all values) from the config file.")
def getconfig(args):
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

    if args.key is None:
        dump(pcot.config.data)
    else:
        # split the provided path into elements
        path = args.key.split(".")
        d = pcot.config.data
        while len(path) > 0:
            key = path[0]
            if key not in d:
                raise KeyError(f"Key '{args.key}' not found in config file")
            d = d[key]
            path = path[1:]
        if isinstance(d, TaggedDict or TaggedList):
            dump(d, args.key)
        else:
            print(d)



@subcommand([
    argument("key", metavar="KEY", help="Name of config item to set"),
    argument("value", metavar="VALUE", help="Value to set the config item to"),
    ],
    shortdesc="Set a value in the config file")
def setconfig(args):
    """
    Set a value in the config file. This is a simple key-value store for the application.
    You can also edit the config file directly - it will be called .pcot.ini in your home
    directory. The key is in the form section.key, where section is the section in the .ini file.
    If the section is Default, you can omit it. See "pcot getconfig -h" to see the current values.
    """
    import pcot.config

    keys = args.key.split(".")
    current = pcot.config.data
    v = args.value

    for i, key in enumerate(keys):
        is_last = (i == len(keys) - 1)

        if key not in current:
            raise KeyError(f"Key '{key}' not found at path: " f"{'.'.join(keys[:i]) or ''}")

        if is_last:
            print("SET")
            tp = current.tag(key).type
            if tp == float:
                v = float(v)
            elif tp == int:
                v = int(v)
            current[key] = v
            pcot.config.save()
            return

        # Not last: must be a dict
        if not isinstance(current[key], (TaggedDict, TaggedList)):
            raise KeyError("Item at "
                f"Item at '{'.'.join(keys[:i+1])}' is not a dict or list, "
                f"but a {type(current[key]).__name__}"
            )

        if isinstance(current[key], TaggedDict):
            current = current[key]
        elif isinstance(current[key], TaggedList):
            try:
                key = int(key)
            except:
                raise KeyError(f"Could not convert '{key}' to int at {'.'.join(keys[:i+1])}")
            current = current[key]


