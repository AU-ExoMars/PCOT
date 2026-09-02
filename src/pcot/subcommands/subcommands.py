"""
The `pcot` command line group. Individual subcommands attach themselves
directly to `cli` using ordinary click decorators (see gencam.py for an
example) - this module only owns the root group: its common options
(--debug, --log-level etc.) and the "dual dispatch" behaviour where
`pcot somefile.pcot` opens the GUI the same way `pcot gencam ...` runs gencam.

Dual dispatch is implemented by overriding Group.resolve_command(), click's
own extension point for choosing which subcommand to run (the same approach
the `click-default-group` package uses): if the first token on the command
line isn't a recognised subcommand name, it's treated as arguments to the
`open` command (defined in main.py) instead of failing with "no such
command". This composes properly with click's own option parsing, so e.g.
`pcot --log-level DEBUG somefile.pcot` isn't confused into thinking "DEBUG" is
the file to open.
"""

import logging
import sys

import click

logger = logging.getLogger(__name__)


class PCOTGroup(click.Group):
    fallback_command_name = "open"

    def resolve_command(self, ctx, args):
        if args and args[0] not in self.commands:
            cmd = self.commands[self.fallback_command_name]
            return self.fallback_command_name, cmd, args
        return super().resolve_command(ctx, args)


def _install_import_monitor():
    print("adding import monitor")

    class ImportMonitor:
        def find_spec(self, fullname, path, target=None):
            print(f"Loading module: {fullname}")
            return None  # Continue normal import process

    sys.meta_path.insert(0, ImportMonitor())


@click.group(cls=PCOTGroup, name="pcot", invoke_without_command=True, no_args_is_help=False,
             context_settings={"help_option_names": ["-h", "--help"]})
@click.option('-d', '--debug', is_flag=True, help="set log level to debug")
@click.option('-v', '--verbose', is_flag=True, help="set log level to verbose (i.e. INFO)")
@click.option('--log-level', 'loglevel_name', help='set log level',
              type=click.Choice(["ERROR", "WARN", "INFO", "DEBUG", "CRITICAL"]))
@click.option('--show-imports', is_flag=True, help="show module imports for debugging")
@click.option('--ignore-version', is_flag=True, help="don't do a version check when loading PCOT documents")
@click.pass_context
def cli(ctx, debug, verbose, loglevel_name, show_imports, ignore_version):
    """PCOT - the PanCam Operations Toolkit."""
    if loglevel_name is not None:
        level = loglevel_name
    elif debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.getLogger("pcot").setLevel(level)

    import pcot.config
    pcot.config.ignore_version = ignore_version

    if show_imports:
        _install_import_monitor()

    if ctx.invoked_subcommand is None:
        # bare "pcot" - run the same fallback command an unrecognised first
        # token would have dispatched to, so a plain "pcot" opens the GUI.
        ctx.invoke(ctx.command.commands[ctx.command.fallback_command_name])
