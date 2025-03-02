# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

from pcot.utils.subcommands import \
    maincommand, subcommand, argument, process, set_common_args
import logging

import sys


# This command line system specifies the "main command", which you get if you
# just give "pcot" on the command line. If the next item is a recognised subcommand
# name, that subcommand will be done instead. The main command and each subcommand
# are defined, with their arguments, by decorators. These are in subcommands.py.

set_common_args([
    argument('--debug', '-d', help="set log level to debug", action="store_const",
             dest="loglevel", const=logging.DEBUG),
    argument('--verbose', '-v', help="set log level to verbose (i.e. INFO)", action="store_const",
             dest="loglevel", const=logging.INFO),
    argument("--log-level", dest="loglevel", help='set log level',
             choices=["ERROR", "WARN", "INFO", "DEBUG", "CRITICAL"]),
    argument("--import-monitor", action="store_true", help="show module imports for debugging")],
    loglevel=logging.WARNING)


# This decorator sets up the main command and arguments it takes.
# There are additional arguments used by the entire system (main command and
# subcommands), which are in subcommands.py.

@maincommand([argument("file", metavar="FILE", help="PCOT file to load", type=str, nargs="?")])
def mainfunc(args):
    """Run the PCOT application, loading any file specified"""
    import pcot.app
    pcot.app.run(args)


#
# This is a test command.
#

@subcommand([
    argument("n", metavar="INT", help="an integer", type=int),
    argument("-q", "--quick", help="some kind of flag", action="store_true")],
    shortdesc="A test command")
def test(args):
    """Does testy things"""
    print(f"Test subcommand: {args.n} {args.quick}")
    logging.getLogger(__name__).debug("foo")


#
# The main function which just runs process() in the subcommands module. This
# will parse the command line and run the appropriate function - either the maincommand
# function or a subcommand.
#
def main():
    logger = logging.getLogger("pcot")  # top level logger
    # get the function to run and arguments to parse
    func, args = process()
    # process the common ags
    logger.setLevel(args.loglevel)
    if args.import_monitor:
        class ImportMonitor:
            def find_spec(self, fullname, path, target=None):
                print(f"Loading module: {fullname}")
                return None  # Continue normal import process

        sys.meta_path.insert(0, ImportMonitor())

    
    # run the function
    func(args)


if __name__ == "__main__":
    main()
