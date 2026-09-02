# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

import logging
import sys

from pcot.subcommands.subcommands import \
    cli, maincommand, argument, set_common_args, peek_remainder, FALLBACK_COMMAND_NAME

# This command line system specifies the "main command", which you get if you
# just give "pcot" on the command line. If the next item is a recognised subcommand
# name, that subcommand will be done instead. The main command and each subcommand
# are defined, with their arguments, by decorators. These are in subcommands.py.
# "Recognised subcommand" is decided by peek_remainder() below, which leniently
# strips the common options (this section) out of argv first, so that e.g.
# `pcot --log-level DEBUG somefile.pcot` isn't confused into thinking "DEBUG" is
# the file to open.

set_common_args([
    argument('--debug', '-d', dest='loglevel', help="set log level to debug", action="store_const",
             const=logging.DEBUG),
    argument('--verbose', '-v', dest='loglevel', help="set log level to verbose (i.e. INFO)", action="store_const",
             const=logging.INFO),
    argument("--log-level", dest="loglevel_name", help='set log level',
             choices=["ERROR", "WARN", "INFO", "DEBUG", "CRITICAL"]),
    argument("--show-imports", action="store_true", help="show module imports for debugging"),
    argument("--ignore-version", action="store_true",
             help="don't do a version check when loading PCOT documents"),
])


def _install_import_monitor():
    print("adding import monitor")

    class ImportMonitor:
        def find_spec(self, fullname, path, target=None):
            print(f"Loading module: {fullname}")
            return None  # Continue normal import process

    sys.meta_path.insert(0, ImportMonitor())


# uncomment this if you want to see every import from startup - but it's better to call
# this from the command line with --show-imports, although that will miss some early imports.
# _install_import_monitor()


def _common_args_callback(loglevel, loglevel_name, show_imports, ignore_version):
    """Runs before any subcommand (or the main command) - applies the common
    options that used to be merged into every subcommand's args namespace."""
    logger = logging.getLogger("pcot")
    logger.setLevel(loglevel_name if loglevel_name is not None else (loglevel or logging.WARNING))

    import pcot.config
    pcot.config.ignore_version = ignore_version

    if show_imports:
        _install_import_monitor()


cli.callback = _common_args_callback


# This decorator sets up the main command and arguments it takes.
# There are additional arguments used by the entire system (main command and
# subcommands), which are in subcommands.py.

@maincommand([
    argument("file", metavar="FILE", help="PCOT file to load", type=str, nargs="?"),
])
def mainfunc(args):
    """Run the PCOT application, loading any file specified"""
    import pcot.app
    pcot.app.run(args)


#
# The main function, which works out whether the user is invoking a
# recognised subcommand or not, and if not inserts the fallback command name
# (FALLBACK_COMMAND_NAME) so that click dispatches to the main/GUI command -
# this is what lets "pcot somefile.pcot" open the GUI, and "pcot gencam ..."
# run a subcommand, from the same top-level command.
#
def main():
    argv = sys.argv[1:]
    remainder = peek_remainder(argv)
    if not remainder or remainder[0] not in cli.commands:
        # the common options are always a prefix of argv (they must come
        # before the subcommand name), so whatever peek_remainder() stripped
        # out was exactly that prefix.
        idx = len(argv) - len(remainder)
        argv = argv[:idx] + [FALLBACK_COMMAND_NAME] + argv[idx:]
    cli.main(args=argv, prog_name="pcot")


if __name__ == "__main__":
    main()
