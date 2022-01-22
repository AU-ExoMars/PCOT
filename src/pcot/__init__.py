import pkgutil

import pcot.macros as macros
import pcot.ui as ui
import pcot.xform as xform
import pcot.xforms
from pcot.config import getUserName, addMainWindowHook, addExprFuncHook
from pcot.utils import archive
from pcot.xforms import *

# get version data, which consists of something like
#   0.0.0  ISO-DATE RAINBOW CODE NAME
tmp = pkgutil.get_data('pcot', 'VERSION.txt')
if tmp is None:
    raise ValueError('cannot find VERSION.txt')

# this string gets turned into pcot.__fullversion__, while pcot.__version__
# is just the number part (0.0.0 in the example).

__fullversion__ = tmp.decode('utf-8')
__version__ = __fullversion__.split(maxsplit=1)[0]

