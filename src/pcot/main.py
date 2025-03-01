# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

from pcot.utils.subcommands import maincommand,subcommand,argument,process
import pcot.app
import logging

logger = logging.getLogger(__name__)

# This command line system specifies the "main command", which you get if you
# just give "pcot" on the command line. If the next item is a recognised subcommand
# name, that subcommand will be done instead. The main command and each subcommand
# are defined, with their arguments, by decorators. These are in subcommands.py.


# This decorator sets up the main command and arguments it takes.
# There are additional arguments used by the entire system (main command and
# subcommands), which are in subcommands.py.

@maincommand([argument("file",metavar="FILE",help="PCOT file to load",type=str,nargs="?")])
def mainfunc(args):
    """Run the PCOT application, loading any file specified"""
    pcot.app.run(args)
    

#
# This is a test command with no arguments.
#

@subcommand(shortdesc="A test command")
def test(args):
    """Does testy things"""
    logger.debug("Test subcommand")
    print("This works")

#
# The main function which just runs process() in the subcommands module. This
# will parse the command line and run the appropriate functio - either the maincommand
# function or a subcommand.
#
def main():
    process()


if __name__ == "__main__":
    main()

