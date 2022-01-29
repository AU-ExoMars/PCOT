import configparser
import getpass
import io
import logging
import os
import pkgutil
from collections import deque

logger = logging.getLogger(__name__)


def getAssetAsString(fn):
    s = pkgutil.get_data('pcot.assets', fn)
    if s is None:
        raise ValueError(f'cannot find asset {fn}')
    return s.decode('utf-8')


def getAssetAsFile(fn):
    return io.StringIO(getAssetAsString(fn))


def getUserName():
    """return the current username, whichis either obtained from the OS or from the PCOT_USER environment variable"""
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


data = None

data = configparser.ConfigParser()
data.read_file(getAssetAsFile('defaults.ini'))
data.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')


def getDef(key, fallback='nofallback'):
    """get a value from the Default section"""
    if fallback == 'nofallback':
        return data['Default'][key]
    else:
        return data['Default'].get(key, fallback=fallback)


class Recents:
    paths = deque()
    COUNT = 5

    @classmethod
    def add(cls, path):
        path = os.path.realpath(path)
        if path in cls.paths:
            cls.paths.remove(path)
        cls.paths.appendleft(path)
        while len(cls.paths) > cls.COUNT:
            cls.paths.pop()

    @classmethod
    def fetch(cls):
        for i in range(cls.COUNT):
            name = "Recent{}".format(i)
            if name in data['Default']:
                cls.paths.append(data['Default'][name])

    @classmethod
    def store(cls):
        for i in range(len(cls.paths)):
            name = "Recent{}".format(i)
            data['Default'][name] = cls.paths[i]


def getRecents():
    return Recents.paths


Recents.fetch()


def save():
    Recents.store()
    with open(os.path.expanduser('~/.pcot.ini'), 'w') as f:
        data.write(f)


def setDefaultDir(kind, directory):
    logger.info(f"Setting default dir for {kind} to {directory}")
    directory = os.path.realpath(directory)
    data['Locations'][kind] = directory
    save()


def getDefaultDir(kind):
    directory = data['Locations'][kind]
    logger.debug(f"Retrieving default dir for {kind} as {directory}")
    return directory


def addRecent(fn):
    fn = os.path.realpath(os.path.expanduser(fn))  # just make sure.
    Recents.add(fn)
    setDefaultDir('pcotfiles', os.path.dirname(fn))
    save()


# These are used to add plugins: main window hooks run when a main window is opened,
# so that new menu items can be added. Expression function hooks run when the
# expression evaluator is initialised, so that new user functions can be added.

mainWindowHooks = []
exprFuncHooks = []


def addMainWindowHook(x):
    mainWindowHooks.append(x)


def addExprFuncHook(x):
    exprFuncHooks.append(x)
