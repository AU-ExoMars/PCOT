"""
This package contains subcommands and the functions they run - if these are of any size,
put them into a separate module and please use local imports within the function (see lscams for details).
"""

from pcot.subcommands.subcommands import \
    maincommand, subcommand, argument, process, set_common_args

# import the subcommand modules - these should only import from other modules locally.
import pcot.subcommands.lscams
import pcot.subcommands.gencam
import pcot.subcommands.parcutils
import pcot.subcommands.config

