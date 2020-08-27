# This fun snippet imports automatically all the xform files in here.

from os.path import dirname, basename, isfile, join
import glob
modules = glob.glob(join(dirname(__file__), "xform*.py"))
__all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]

for x in __all__:
    print("Importing ",x)
