"""
This package contains subcommands and the functions they run - if these are of any size,
put them into a separate module and please use local imports within the function (see lscams for details).
"""

from pcot.subcommands.subcommands import cli

# import the subcommand modules - these register themselves onto `cli` via
# @cli.command(), and should only import from other modules locally.
import pcot.subcommands.lscams
import pcot.subcommands.config
import pcot.subcommands.batch
import pcot.subcommands.parcutils
import pcot.subcommands.gencam
import pcot.subcommands.genrefl
import pcot.subcommands.lsrefls

