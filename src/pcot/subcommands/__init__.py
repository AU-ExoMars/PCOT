"""
This package contains subcommands and the functions they run - if these 
are of any size, the bulk of the code should be in a separate module which
is imported on demand when their function runs.
"""

from pcot.subcommands.subcommands import \
    maincommand, subcommand, argument, process, set_common_args


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


@subcommand([
    argument('params',type=str,metavar='YAML_FILENAME',help="Input YAML file with parameters"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename")
    ],
    shortdesc="Process a YAML camera file into a PARC file")
    
def gencam(args):
    from .gencam import run
    run(args)
    
    
    
    
    
