import pkgutil

import pcot.macros as macros
import pcot.ui as ui
import pcot.xform as xform
import pcot.xforms
from pcot.config import getUserName, addMainWindowHook, addExprFuncHook
from pcot.utils import archive
from pcot.xforms import *

tmp = pkgutil.get_data('pcot', 'VERSION.txt')
if tmp is None:
    raise ValueError('cannot find VERSION.txt')

__version__ = tmp.decode('utf-8')

