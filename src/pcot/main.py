# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

import logging
import sys

import click

from pcot.subcommands.subcommands import \
    cli, maincommand, argument, set_common_args

# This command line system specifies the "main command", which you get if you
# just give "pcot" on the command line. If the next item is a recognised subcommand
# name, that subcommand will be done instead. The main command and each subcommand
# are defined, with their arguments, by decorators. These are in subcommands.py.
# The dispatch itself is PCOTGroup.resolve_command(), in subcommands.py.

set_common_args([
    argument('--debug', '-d', help="set log level to debug", action="store_true"),
    argument('--verbose', '-v', help="set log level to verbose (i.e. INFO)", action="store_true"),
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


def _common_args_callback(debug, verbose, loglevel_name, show_imports, ignore_version):
    """Runs before any subcommand (or the main command) - applies the common
    options that used to be merged into every subcommand's args namespace."""
    logger = logging.getLogger("pcot")
    if loglevel_name is not None:
        level = loglevel_name
    elif debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logger.setLevel(level)

    import pcot.config
    pcot.config.ignore_version = ignore_version

    if show_imports:
        _install_import_monitor()

    # invoke_without_command means we also get called with nothing following
    # (bare "pcot") - in that case run the fallback (GUI) command ourselves,
    # the same command resolve_command() would have picked for an unrecognised
    # first token.
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        ctx.invoke(cli.commands[cli.fallback_command_name])


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


def main():
    cli.main(prog_name="pcot")


if __name__ == "__main__":
    main()
