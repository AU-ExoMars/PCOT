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
    if args.key is None:
        for section in pcot.config.data:
            for key in pcot.config.data[section]:
                print(f"{section}.{key} = {pcot.config.data[section][key]}")
    else:
        # we want to show all sections, so split the key into sections and key
        if '.' in args.key:
            section, key = args.key.split('.', 1)
        else:
            section, key = 'Default', args.key
        if section not in pcot.config.data:
            raise ValueError(f"Section '{section}' is not in the config file")
        if key not in pcot.config.data[section]:
            raise ValueError(f"Key {key} is not in the config file in section '{section}'")
        print(f"{section}.{key} = {pcot.config.data[section][key]}")


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
    # we want to show all sections, so split the key into sections and key
    if '.' in args.key:
        section, key = args.key.split('.', 1)
    else:
        section, key = 'Default', args.key
    if section not in pcot.config.data:
        raise ValueError(f"Section '{section}' is not in the config file")
    if key not in pcot.config.data[section]:
        print(f"Adding {section}.{key} = {args.value}")
    else:
        print(f"Setting {section}.{key} = {args.value}")

    pcot.config.data[section][key] = args.value
    pcot.config.save()


