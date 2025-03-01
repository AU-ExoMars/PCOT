"""Code from https://gist.github.com/mivade/384c2c41c3a29c637cb6c603d4197f9f

which was released into the public domain.

This wraps the argparse code with some nice decorators. I've also made some 
nasty modifications so that (a) the null subcommand exists (i.e. no subcommand given)
and (b) information on the subcommands is given in usage and help.


"""

from argparse import ArgumentParser
from dataclasses import dataclass
import logging

subcommand_parser = ArgumentParser()
subparsers = subcommand_parser.add_subparsers(dest="subcommand")
subcommands = {}
main_command = None
mainfunc = None

# This parser parses the common arguments to both main and subcommands
# We don't want to add a help argument to avoid the common parser parsing
# it and exiting early.
common_parser = ArgumentParser(add_help=False)


def set_common_args(args, **kwargs):
    """Provide common arguments and defaults (the latter as keyword args
    like set_defaults() in argparse"""
    for arg in args:
        common_parser.add_argument(*arg[0], **arg[1])
    common_parser.set_defaults(**kwargs)


@dataclass
class CommandInfo:
    parser: ArgumentParser
    shortdesc: str


def argument(*name_or_flags, **kwargs):
    """Convenience function to properly format arguments to pass to the
    subcommand decorator.

    """
    return list(name_or_flags), kwargs


def subcommand(args=None, shortdesc="", parent=subparsers):
    """Decorator to define a new subcommand in a sanity-preserving way.

    Usage example::

        # set up a common argument and default for it - these come before the subcommand,
        # e.g. prog -d mysubcommand foo
        #   * prog is main program
        #   * -d is a common argument
        #   * mysubcommand is a subcommand
        *   * foo is an argument to that subcommand        
 
        set_common_args([
            argument('--debug','-d',help="set log level to debug",action="store_const",
                dest="loglevel",const=logging.DEBUG)],
            loglevel=logging.WARNING)
    
        @maincommand([argument("zog", help="Argument for main command",type=str)])
        def mainfunc(args):
            print(args.zog)

        @subcommand([argument("-d", help="Enable debug mode", action="store_true")],"does a thing")
        def mysubcommand(args):
            print(args)
            
        def main():
            # get the function to run and arguments to parse
            func, args = process()
            # process the common args (an example)
            logger.setLevel(args.loglevel)
            # run the function
            func(args)
    """

    def decorator(func):
        parser = parent.add_parser(func.__name__, description=func.__doc__)
        if args:
            for arg in args:
                parser.add_argument(*arg[0], **arg[1])
        parser.set_defaults(func=func)
        subcommands[func.__name__] = CommandInfo(parser, shortdesc)

    return decorator


class MainArgumentParser(ArgumentParser):
    """
    This is pretty grim. It overrides the formatting code to add information on
    subcommands, and it does so using a lot of argparse internals."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_subcommand_info(self, formatter):
        formatter.start_section("The following subcommands also exist")
        # first, assemble pairs of strings that will be put into columns
        columns = []
        for k, i in subcommands.items():
            p = i.parser
            # nasty hackery to get the usage string out of the subcommand
            ff = i.parser._get_formatter()
            ff._prog = f"{self.prog} {k}"
            ff.add_usage(p.usage, p._actions, p._mutually_exclusive_groups, "")
            ss = ff.format_help().strip()
            # first column is usage, second is shortdescription
            columns.append((ss, i.shortdesc))
        # find the maximum width of the first column            
        maxw = max([len(x[0]) for x in columns])
        # now output

        for x, y in columns:
            # we add the columns to the formatter, but we pass it through
            # an identity function to format it so no wrapping or filling
            # will happen.
            ss = f"{x.ljust(maxw)}   :   {y}\n"
            formatter._add_item((lambda x: x), (ss,))

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
        global main_command
        global mainfunc
        p = MainArgumentParser()
        p.description = func.__doc__
        main_command = CommandInfo(p, func.__doc__)
        mainfunc = func
        for arg in args:
            main_command.parser.add_argument(*arg[0], **arg[1])

    return decorator


def update_args(args, args_to_add):
    # add the args_to_add to the args Namespace
    for k, v in vars(args_to_add).items():
        setattr(args, k, v)


def process():
    """Process the arguments.
    Return value: a tuple of
        * command function to call
        * argument list for the function (with common arguments merged in)
    This is so that we can process the common args in a common way before calling the
    function."""

    import sys
    global subcommand_help
    logger = logging.getLogger("pcot")

    # parse the common arguments and get the remaining args
    # return value is remaining args, args namespace.

    (common_args, argv) = common_parser.parse_known_args()
    # if the first non-dash argument is a command, and there a main function,
    # use that.

    lst = [x for x in argv if x[0] != '-']

    if mainfunc and (len(lst) < 1 or lst[0] not in subcommands):
        # parse main program args
        args = main_command.parser.parse_args(argv)
        # merge in the common args
        update_args(args, common_args)
        func = mainfunc
    else:
        # parse common args
        args = subcommand_parser.parse_args(argv)
        # merge in the common args
        update_args(args, common_args)
        if args.subcommand is None:  # ???? WHY MIGHT THIS HAPPEN
            print("Null subcommand")
            subcommand_parser.print_help()
        else:
            func = args.func

    return func, args
