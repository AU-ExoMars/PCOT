import traceback

try:
    import pcot.macros as macros
except AttributeError as e:
    traceback.print_exc()
    print("""
    This error MAY mean that you should turn off Qt Compatible debugging in PyCharm. It's a bug
    https://youtrack.jetbrains.com/issue/PY-50959
    """)
    exit(0)

import pcot.ui as ui
import pcot.xform as xform
import pcot.xforms
from pcot.config import getUserName, addMainWindowHook, addExprFuncHook
from pcot.utils import archive
from pcot.xforms import *
import logging
import pkgutil

import faulthandler

faulthandler.enable()


def setup():
    """Call this to initialise PCOT. We could just call it here, but other things would break then.
    You'll see that main() calls it."""

    # forces the file to be parsed, which uses decorators to register functions etc.
    import pcot.expressions.builtins

    # creates xform type singletons, which also causes the expression evaluator to be
    # created as part of XFormExpr, running the functions registered above and thus
    # allowing *them* to register functions etc.
    xform.createXFormTypeInstances()

    # load filter data from both built in files (PANCAM and AUPE) and others.
    config.loadFilters()

    # If we run without a GUI, we still need an application. This will provide that.
    from pcot.main import checkApp
    checkApp()


logging.basicConfig(format='%(levelname)s %(asctime)s %(name)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# matplotlib spews a lot of debugging data - turn it off
logging.getLogger('matplotlib.font_manager').disabled = True


logger.info("Starting PCOT")

# get version data, which consists of something like
#   0.0.0  ISO-DATE RAINBOW CODE NAME
tmp = pkgutil.get_data('pcot', 'VERSION.txt')
if tmp is None:
    raise ValueError('cannot find VERSION.txt')

# this string gets turned into pcot.__fullversion__, while pcot.__version__
# is just the number part (0.0.0 in the example).

__fullversion__ = tmp.decode('utf-8').strip()
__version__ = __fullversion__.split(maxsplit=1)[0]
