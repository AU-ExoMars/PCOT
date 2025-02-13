import configparser
import getpass
import importlib.resources
import io
import logging
import os
import pkgutil
from collections import deque

from PySide2 import QtWidgets

logger = logging.getLogger(__name__)


def getAssetAsString(fn, package="pcot.assets"):
    s = pkgutil.get_data(package, fn)
    if s is None:
        raise ValueError(f'cannot find asset {fn}')
    return s.decode('utf-8')


def getAssetAsFile(fn, package="pcot.assets"):
    return io.StringIO(getAssetAsString(fn, package=package))


def getAssetPath(fn, package="pcot.assets"):
    with importlib.resources.path(package, fn) as p:
        return p


def getUserName():
    """return the current username, whichis either obtained from the OS or from the PCOT_USER environment variable"""
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


data = configparser.ConfigParser()
data.read_file(getAssetAsFile('defaults.ini'))
data.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')


def str2bool(s):
    """intelligently (heh) convert a string to a bool - for use in config data"""
    return s.lower() in ["yes", "1", "y", "true", "t", "on"]


def getDef(key, fallback='nofallback'):
    """get a value from the Default section"""
    if fallback == 'nofallback':
        return data['Default'][key]
    else:
        return data['Default'].get(key, fallback=fallback)


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

    def fetch(self,config_data):
        for i in range(self.count):
            name = "Recent{}".format(i)
            if name in data['Default']:
                self.paths.append(config_data['Default'][name])

    def store(self, config_data):
        for i in range(len(self.paths)):
            name = "Recent{}".format(i)
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
    logger.debug(f"Setting default dir for {kind} to {directory}")
    directory = os.path.realpath(directory)
    data['Locations'][kind] = directory
    save()


def getDefaultDir(kind):
    directory = data['Locations'][kind]
    logger.debug(f"Retrieving default dir for {kind} as {directory}")
    return directory


def addRecent(fn):
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


def loadFilters():
    """Load the default filter sets from the resource directory, followed by user filters
    as specified in the .ini file."""
    from pcot.filters import loadFilterSet
    from pathlib import Path

    # these can be overridden by the data in the config file
    loadFilterSet('AUPE', getAssetPath('aupe.csv'))
    loadFilterSet('PANCAM', getAssetPath('pancam.csv'))

    if 'filters' in data:
        for name in data['filters']:
            file = data['filters'][name]
            loadFilterSet(name, Path(file))


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


# significant figures to display for Values
sigfigs = int(getDef('sigfigs', '5'))
