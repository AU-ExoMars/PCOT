"""Code from https://gist.github.com/mivade/384c2c41c3a29c637cb6c603d4197f9f

which was released into the public domain.

This wraps the argparse code with some nice decorators. I've also made some 
nasty modifications so that (a) the null subcommand exists (i.e. no subcommand given)
and (b) information on the subcommands is given in usage and help.


"""

from argparse import ArgumentParser, HelpFormatter
from dataclasses import dataclass
import logging

subcommand_parser = ArgumentParser()
subparsers = subcommand_parser.add_subparsers(dest="subcommand")
subcommands = {}
mainparser = None
mainfunc = None

# add logger args

def addLoggerArgs(p):
    p.set_defaults(loglevel=logging.WARNING)
    p.add_argument('--debug','-d',help="set log level to debug",
        action="store_const",dest="loglevel",const=logging.DEBUG) 
    p.add_argument('--verbose','-v',help="set log level to verbose (i.e. INFO)",
        action="store_const",dest="loglevel",const=logging.INFO) 

addLoggerArgs(subcommand_parser)

@dataclass
class SubcommandInfo:
    parser: ArgumentParser
    shortdesc: str
    

def argument(*name_or_flags, **kwargs):
    """Convenience function to properly format arguments to pass to the
    subcommand decorator.

    """
    return (list(name_or_flags), kwargs)
    
def subcommand(args=[], shortdesc="", parent=subparsers):
    """Decorator to define a new subcommand in a sanity-preserving way.
    The function will be stored in the ``func`` variable when the parser
    parses arguments so that it can be called directly like so::

        args = subcommand_parser.parse_args()
        args.func(args)

    Usage example::
    
        @maincommand([argument("zog", help="Argument for main command",type=str)])
        def mainfunc(args):
            print(args.zog)

        @subcommand([argument("-d", help="Enable debug mode", action="store_true")],"does a thing")
        def subcommand(args):
            print(args)

    Then on the command line::

        $ python cli.py subcommand -d
        
    Or
        $ python cli.py myzogstring

    to run the "main command"
    """
    
    def decorator(func):
        parser = parent.add_parser(func.__name__, description=func.__doc__)
        for arg in args:
            parser.add_argument(*arg[0], **arg[1])
        parser.set_defaults(func=func)
        subcommands[func.__name__] = SubcommandInfo(parser,shortdesc)
    return decorator
    

class MainArgumentParser(ArgumentParser):
    """
    This is pretty grim. It overrides the formatting code to add information on
    subcommands, and it does so using a lot of argparse internals."""
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)

    def add_subcommand_info(self,formatter):
        formatter.start_section("The following subcommands also exist")
        # first, assemble pairs of strings that will be put into columns
        columns = []
        for k,i in subcommands.items():
            p = i.parser
            # nasty hackery to get the usage string out of the subcommand
            ff = i.parser._get_formatter()
            ff._prog = f"{self.prog} {k}"
            ff.add_usage(p.usage,p._actions,p._mutually_exclusive_groups,"")
            ss = ff.format_help().strip()
            # first column is usage, second is shortdescription
            columns.append((ss,i.shortdesc))
        # find the maximum width of the first column            
        maxw = max([len(x[0]) for x in columns])
        # now output
        
        for x,y in columns:
            # we add the columns to the formatter, but we pass it through
            # an identity function to format it so no wrapping or filling
            # will happen.
            ss = f"{x.ljust(maxw)}   :   {y}\n"
            formatter._add_item((lambda x: x),(ss,))
            
            
        formatter.end_section()
        
        
    def format_usage(self):
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)
        self.add_subcommand_info(formatter)

        return formatter.format_help()
    
    def format_help(self):
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        # epilog
            formatter.add_text(self.epilog)

        # jcf - add subcommand data
        self.add_subcommand_info(formatter)

        # determine help from format above
        return formatter.format_help()
    
    

    
def maincommand(args=[]):
    def decorator(func):
        global mainparser
        global mainfunc
        mainparser = MainArgumentParser()
        addLoggerArgs(mainparser)
        mainfunc = func
        for arg in args:
            mainparser.add_argument(*arg[0], **arg[1])
    return decorator
            


def process():
    import sys
    global subcommand_help
    logger = logging.getLogger("pcot")
    
    # make a copy of the arg list with the "-" arguments stripped
    lst = [x for x in sys.argv[1:] if x[0]!="-"]
    # if the first non-dash argument is not a command, and there a main function,
    # use that.
    if mainfunc and (len(lst)<1 or lst[0] not in subcommands):
        args = mainparser.parse_args()
        logger.setLevel(args.loglevel)
        mainfunc(args)
    else:
        args = subcommand_parser.parse_args()
        logger.setLevel(args.loglevel)
        if args.subcommand is None:
            subcommand_parser.print_help()
        else:
            args.func(args)
