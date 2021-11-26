# This fun snippet imports automatically all the xform files in here.

import glob
import pkgutil
import sys
from os.path import dirname, basename, isfile, join

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # we are running a frozen build so can't get a submodule list from the filesystem.
    # However, the freezer (pyinstaller) should have created a list.
    tmp = pkgutil.get_data('pcot', 'xformlist.txt')
    xformlist = tmp.decode('utf-8')
    __all__ = xformlist.strip().split()
else:
    # this way doesn't work with pyinstaller
    modules = glob.glob(join(dirname(__file__), "xform*.py"))
    __all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]

for x in __all__:
    print("Importing ", x)
