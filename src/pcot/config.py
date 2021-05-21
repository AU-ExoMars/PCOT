import configparser
import getpass
import io
import os

from pkg_resources import resource_string as resource_bytes
from collections import deque


def getAssetAsFile(fn):
    s = resource_bytes('pcot.assets', fn).decode('utf-8')
    return io.StringIO(s)


## return the current username, whichis either obtained from the OS
# or from the PCOT_USER environment variable

def getUserName():
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


data = None

data = configparser.ConfigParser()
data.read_file(getAssetAsFile('defaults.ini'))
data.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')

locations = data['Locations']
default = data['Default']


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
            if name in default:
                cls.paths.append(default[name])

    @classmethod
    def store(cls):
        for i in range(len(cls.paths)):
            name = "Recent{}".format(i)
            default[name] = cls.paths[i]


def getRecents():
    return Recents.paths


Recents.fetch()


def save():
    Recents.store()
    with open(os.path.expanduser('~/.pcot.ini'), 'w') as f:
        data.write(f)


def addRecent(fn):
    fn = os.path.realpath(os.path.expanduser(fn))  # just make sure.
    Recents.add(fn)
    locations['pcotfiles'] = fn
    save()
