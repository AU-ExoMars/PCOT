import configparser
import getpass
import logging
import os
from collections import deque
from PySide2 import QtWidgets

from pcot.assets import getAssetAsFile

logger = logging.getLogger(__name__)

# create the config parser
data = configparser.ConfigParser()
data.optionxform = str  # make it case sensitive

main_app_running = False        # set when we are actually running the GUI

# load the defaults.ini file first
data.read_file(getAssetAsFile('defaults.ini'))
# and then the site.cfg and user's .pcot.ini file, overriding the defaults
data.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')

xxx = data.get('Default', 'multifile_pattern')


def getUserName():
    """return the current username, whichis either obtained from the OS or from the PCOT_USER environment variable"""
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


def str2bool(s):
    """intelligently (heh) convert a string to a bool - for use in config data"""
    return s.lower() in ["yes", "1", "y", "true", "t", "on"]


class Recents:
    def __init__(self, count):
        self.paths = deque()
        self.count = count

    def add(self, path):
        path = os.path.realpath(path)
        if path in self.paths:
            self.paths.remove(path)
        self.paths.appendleft(path)
        while len(self.paths) > self.count:
            self.paths.pop()

    def fetch(self, config_data):
        for i in range(self.count):
            name = "recent{}".format(i)
            if name in data['Default']:
                self.paths.append(config_data['Default'][name])

    def store(self, config_data):
        for i in range(len(self.paths)):
            name = "recent{}".format(i)
            config_data['Default'][name] = self.paths[i]


# create and load the recent files singleton
_recents = Recents(5)
_recents.fetch(data)


def getRecents():
    return _recents.paths


def save():
    _recents.store(data)
    with open(os.path.expanduser('~/.pcot.ini'), 'w') as f:
        data.write(f)


def setDefaultDir(kind, directory):
    if main_app_running:
        logger.debug(f"Setting default dir for {kind} to {directory}")
        directory = os.path.realpath(directory)
        data['Locations'][kind] = directory
        save()


def getDefaultDir(kind):
    directory = data['Locations'].get(kind, None)
    logger.debug(f"Retrieving default dir for {kind} as {directory}")
    return directory


def addRecent(fn):
    """Add a file to the list of recent files. We don't do this outside the main app!"""
    if main_app_running:
        fn = os.path.realpath(os.path.expanduser(fn))  # just make sure.
        _recents.add(fn)
        setDefaultDir('pcotfiles', os.path.dirname(fn))
        save()


def getFileDialogOptions():
    """There is a problem in the Qt->native file dialog code which causes native file dialogs to crash
    on some systems. For that reason, I'm defaulting to the Qt implementations.
    """
    if not str2bool(data['Default'].get('nativefiledialog', 'no')):
        return QtWidgets.QFileDialog.DontUseNativeDialog
    else:
        return QtWidgets.QFileDialog.Options()


def loadCameras():
    """Load the camera data from the archive"""

    from pcot import cameras
    logger.debug("Attempting to load cameras")
    if 'cameras' in data['Locations']:
        path = getDefaultDir('cameras')
        logger.debug(f"Camera directory is {path}")
        if path:
            cameras.loadAllCameras(path)


# These are used to add plugins: main window hooks run when a main window is opened,
# so that new menu items can be added. Expression function hooks run when the
# expression evaluator is initialised, so that new user functions can be added.

mainWindowHooks = []
exprFuncHooks = []


def addMainWindowHook(x):
    """Call this function with another function, which takes a MainWindow. It is called when that window is
    created and can be used to add (say) menu items to the window."""
    mainWindowHooks.append(x)


def executeWindowHooks(x):
    """Execute the window hooks on a given MainWindow"""
    for f in mainWindowHooks:
        f(x)


def addExprFuncHook(x):
    """Call this function with another function. This function is called with a Parser argument, and can add
    new functions, operators and properties. Consider using the @parserhook decorator instead - it does the
    same thing."""
    logger.debug(f"Adding parser hook {x}")
    exprFuncHooks.append(x)


def parserhook(f):
    """This is a decorator used to register a parser callback - the decorated function will be called at startup
    with a Parser object to which functions, operators and properties can be added."""
    addExprFuncHook(f)
    return f


def executeParserHooks(p):
    """Execute the parser callbacks on the given parser"""
    for f in exprFuncHooks:
        f(p)


###### Handy getters for config data - we don't provide fallbacks, the default must be in defaults.ini

def get(key, section='Default'):
    return data.get(section, key)


def getfloat(key, section='Default'):
    return data.getfloat(section, key)


def getint(key, section='Default'):
    return data.getint(section, key)


def getboolean(key, section='Default'):
    return data.getboolean(section, key)
