# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

from pcot.utils.subcommands import maincommand,subcommand,argument,process
import pcot.app
import logging

logger = logging.getLogger(__name__)

@maincommand([argument("file",metavar="FILE",help="PCOT file to load",type=str,nargs="?")])
def mainfunc(args):
    pcot.app.run(args)
    

@subcommand(shortdesc="A test command")
def test(args):
    """Does testy things"""
    logger.debug("Test subcommand")
    print("This works")

def main():
    process()

if __name__ == "__main__":
    main()

