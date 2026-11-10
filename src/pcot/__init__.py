import importlib.util
import os
import re
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
from pcot.utils import archive, spectralparameters
from pcot.xforms import *
import logging
import pkgutil

import faulthandler

faulthandler.enable()

plugins_loaded = False


def load_plugins():
    """plugin dirs are semicolon separated, stored in Locations/plugins"""

    import sys

    # make sure this only happens once - we can call pcot.setup() lots
    # of times during tests.

    global plugins_loaded
    if plugins_loaded:
        return
    plugins_loaded = True

    pluginDirs = pcot.config.getDefaultDir('pluginpath')

    # Load any plugins by recursively walking the plugin directories and importing .py files.

    for d in pluginDirs:
        for root, dirs, files in os.walk(d):
            for filename in files:
                base, ext = os.path.splitext(filename)
                if ext == '.py':
                    path = os.path.join(root, filename)
                    logger.info(f"Loading plugin : {path}")
                    spec = importlib.util.spec_from_file_location(base, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[base] = module
                    spec.loader.exec_module(module)


def setup():
    """Call this to initialise PCOT. We could just call it here, but other things would break then.
    You'll see that main() calls it."""

    # forces the file to be parsed, which uses decorators to register functions etc.
    import pcot.expressions.register
    # force import of builtin functions!
    import pcot.datumfuncs
    # register the built-in ancillary data (sidecar) loaders - before plugins, so they're tried first
    import pcot.ancillary

    load_plugins()

    # creates xform type singletons, which also causes the expression evaluator to be
    # created as part of XFormExpr, running the functions registered above and thus
    # allowing *them* to register functions etc.
    xform.createXFormTypeInstances()

    # load camera set data
    config.loadCameras()
    # and reflectances
    config.loadReflectances()

    spectralparameters.loadSpectralParameters()


    # If we run without a GUI, we still need an application. This will provide that.
    from pcot.app import checkApp
    checkApp()


logging.basicConfig(format='%(levelname)s %(asctime)s %(name)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# matplotlib spews a lot of debugging data - turn it off
logging.getLogger('matplotlib.font_manager').disabled = True


logger.debug("Starting PCOT")

# get version data, which consists of something like
#   0.0.0  ISO-DATE RAINBOW CODE NAME
tmp = pkgutil.get_data('pcot', 'VERSION.txt')
if tmp is None:
    raise ValueError('cannot find VERSION.txt')

# this string gets turned into pcot.__fullversion__, while pcot.__version__
# is just the first word (0.0.0 in the example). That word must be a PEP 440 version
# (e.g. 1.2.0, or 1.2.0b1 for a pre-release) identical to the version in pyproject.toml;
# tests/config/test_version_check.py checks both of these.

# There's a second line too, which is the oldest document version we can safely load.from

tmp = tmp.decode('utf-8')
lines = tmp.splitlines()

__fullversion__ = lines[0].strip()
__version__ = __fullversion__.split(maxsplit=1)[0]

oldest_valid_version = lines[1].split(maxsplit=1)[0]

def compatible_version_check(version):
    """This checks to see if this version of PCOT can load data created by the version passed in"""

    def _do_check(version):
        # remove any trailing stuff from the document version
        version = version.split()[0]

        def _parse(v):
            # take the leading digits of each part, dropping any pre-release suffix: both
            # the old "0.12.0-beta" style found in older documents and PEP 440 "1.1.0b1"
            return tuple(int(re.match(r"\d+", part).group()) for part in v.split("."))

        doc_maj, doc_min, doc_patch = _parse(version)
        app_maj, app_min, app_patch = _parse(oldest_valid_version)

        if doc_maj > app_maj:
            return True
        if doc_maj < app_maj:
            return False

        # major versions the same; check minor
        if doc_min > app_min:
            return True
        if doc_min < app_min:
            return False

        # major and minor the same, check patch
        return doc_patch >= app_patch

    result = _do_check(version)
    if not result:
        if config.ignore_version:
            logger.warning(f"PCOT version {version} does not match PCOT version {oldest_valid_version}")
            return True
    return result
