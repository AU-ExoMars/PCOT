"""
Configuration data system, also handles hooks for plugins
"""
import getpass
import logging
import os
from collections import deque
from pathlib import Path
from typing import Optional, List

import yaml
from PySide6 import QtWidgets

from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedDict, TaggedListType
from pcot.utils.demosaicing import VALID_BAYER_PATTERNS

logger = logging.getLogger(__name__)

# location of the config file
CONFIG_PATH = Path('~/pcot_config.yaml').expanduser()

# This is the TaggedDictType for the configuration system. It doesn't contain
# the recent files list; that's handled by storing it as a separate part
# of the YAML file. The main config is saved under the "configuration" section
# of the YAML.

CONFIG_DICT_TYPE = TaggedDictType(
    loadfile=("File to load by default at startup, or empty",Maybe(Path),None, "*.pcot"),
    sigfigs=("Significant figures for numeric output",int, 5, (0,12)),
    multifile_pattern=("Default regex for getting filter data from filenames in multifile loader", str, r".*[LR](?P<pos>[0-9][0-9]).*"),
    default_camera=("Default camera",str, "PANCAM"),
    defaultbayerpattern=("Default Bayer pattern (see OpenCV docs)", str, "RGGB", VALID_BAYER_PATTERNS),

    locations=("Locations", TaggedDictType(
        images=("Source image default location", Path, os.path.expanduser("~/Pictures"), True),
        mplplots=("Matplotlib outputs default location", Path, Path.home(), True),
        savedimages=("Default location for saving images", Path, Path.home() / "Pictures", True),
        pcotfiles=("Default location for PCOT documents", Path, Path.home(), True),
        pluginpath=("Locations for plugins", TaggedListType(Path, [Path.home() / "pcotplugins"], deflt_append=Path(), valid_choices=True)),
        cameras=("Location of camera files", Maybe(Path), None, True),        # will be initialised on load if not present
        reflectances=("Location of reflectance files", Maybe(Path), None, True), # will be initialised on load if not present
        macrosandfaves=("List of macro and favourites archives", TaggedListType(Path,[], deflt_append=Path.home()/"archive.pcot", valid_choices=False)),
    ).setOrdered(), None),

    testpds4data=("Location of testpds4data files (testing only)",Maybe(Path),None, True),
    nativefiledialog=("Use the native file dialog (best not)", bool, False),
    # "auto" forces XWayland on GNOME/Wayland to work around a dialog decoration bug there;
    # "native" always uses Qt's own platform choice; "xcb" always forces XWayland.
    qt_platform=("Qt platform plugin selection on Linux", str, "auto", ["auto", "native", "xcb"]),

).setOrdered()

# the actual config data, which gets created by load_config()
data:Optional[TaggedDict] = None


main_app_running = False        # set when we are actually running the GUI



def getUserName():
    """return the current username, whichis either obtained from the OS or from the PCOT_USER environment variable"""
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


class Recents:
    """
    Class for managing the list of recent files
    """
    def __init__(self, count):
        self.paths = deque()
        self.count = count

    def add(self, path):
        path = os.path.realpath(path)
        if path in self.paths:
            self.paths.remove(path)
        self.paths.appendleft(path)
        self.ensure_length()

    def ensure_length(self):
        while len(self.paths) > self.count:
            self.paths.pop()

    def deserialise(self, lst:List[str]):
        """Just build the recents object from a list"""
        self.paths = deque(lst)
        self.ensure_length()

    def serialise(self):
        """Return the recent files as a list for serialization"""
        return list(self.paths)

_recents:Optional[Recents] = None

def getRecents():
    if _recents is None:
        raise Exception("Configuration not yet loaded")
    return _recents.paths

def load_config():
    """Read the configuration data into the TaggedDict and recents list"""
    global _recents
    global data
    _recents = Recents(5)

    # create a new config dict with the defaults (some of which will
    # be None and need to be set here)
    # load if it is present, otherwise just create a new one
    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH, 'r') as f:
            # get the serialized YAML data
            s = yaml.load(f, Loader=yaml.SafeLoader)
            conf = s['configuration']
            # legacy data has dodgy patterns
            if conf['defaultbayerpattern'] not in VALID_BAYER_PATTERNS:
                conf['defaultbayerpattern'] = "RGGB"
            # the recent files are in a separate section from the main config
            data = CONFIG_DICT_TYPE.deserialise(conf)
            _recents.deserialise(s['recents'])
    else:
        data = CONFIG_DICT_TYPE.create()
        # recents will be empty


def save():
    """Write the configuration TaggedDict and recent files data to a YAML file"""
    with open(CONFIG_PATH, 'w') as f:
        # serialise as a full dict so we can edit it!
        s = data.serialise(forceUnordered=True)
        out = {
            'configuration': s,
            'recents': _recents.serialise(),
        }
        yaml.dump(out, f, Dumper=yaml.SafeDumper)



def setDefaultDir(kind, directory):
    if main_app_running:
        logger.debug(f"Setting default dir for {kind} to {directory}")
        directory = os.path.realpath(directory)
        data.locations[kind] = directory
        save()


def getDefaultDir(kind):
    directory = data.locations[kind]
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
    if data.nativefiledialog:
        return QtWidgets.QFileDialog.Option(0)
    else:
        return QtWidgets.QFileDialog.Option.DontUseNativeDialog


def loadCameras():
    """Load the camera data from the cameras directory"""

    from pcot import cameras
    logger.debug("Attempting to load cameras")
    path = getDefaultDir('cameras')
    logger.debug(f"Camera directory is {path}")
    if path:
        cameras.loadAllCameras(path)

def loadReflectances():
    """Load the reflectance target data  from the reflectances directory"""

    from pcot import cameras
    logger.debug("Attempting to load reflectances")
    path = getDefaultDir('reflectances')
    if path:
        cameras.loadAllReflectances(path)



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


# first time running, load the data

if data is None:
    logger.info("Loading config data")
    load_config()
#    print(yaml.dump(data.serialise(forceUnordered=True)))