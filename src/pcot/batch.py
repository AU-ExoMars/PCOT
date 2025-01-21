"""
The batch file runner
"""

import logging
import argparse
from pathlib import Path
import jinja2

import pcot
from pcot.parameters.runner import Runner

logger = logging.getLogger(__name__)

# we may need to modify this to permit running multiple batch files!

parser = argparse.ArgumentParser(description="Run a PCOT batch (parameter) file")
parser.add_argument("doc", help="The document to open")
parser.add_argument("file", help="The batch file to run")
parser.add_argument("-l", "--log", help="set debugging level", default="info")
parser.add_argument('vars', nargs='*', help='variables to set in the batch file (vars[0], vars[1], ...)')


def main():
    args = parser.parse_args()
    logging.getLogger("pcot").setLevel(args.log.upper())

    pcot.setup()
    jinja_env = jinja2.Environment()
    jinja_env.globals['vars'] = args.vars

    runner = Runner(Path(args.doc), jinja_env)
    runner.run(Path(args.file))
