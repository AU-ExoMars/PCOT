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


logging.basicConfig(format='%(levelname)s %(asctime)s %(name)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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


