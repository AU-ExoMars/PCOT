"""
This package handles and contains assets, usually strings but some binaries.
"""
import importlib
import importlib.resources
import pkgutil

from PySide6.QtGui import QIcon

from pcot.ui.theme import isDarkMode


def getAssetAsString(fn, package="pcot.assets"):
    """Find a file in the assets package and return its contents as a string, assuming it is utf-8 encoded"""
    s = pkgutil.get_data(package, fn)
    if s is None:
        raise ValueError(f'cannot find asset {fn}')
    return s.decode('utf-8')


def getAssetPath(fn, package="pcot.assets"):
    """Find a file in the assets package and return its path. The file may be in a
    subdirectory of the package, in which case use '/' to separate path components
    (regardless of platform)."""
    resource = importlib.resources.files(package)
    for part in fn.split('/'):
        resource = resource / part
    with importlib.resources.as_file(resource) as p:
        return p


class Icons:
    icons = {}
    @classmethod
    def get(cls, name):
        if isDarkMode():
            name = name + "-darkmode"

        if name not in cls.icons:
            icon = QIcon(str(getAssetPath(name+".svg")))
            cls.icons[name] = icon
        return cls.icons[name]
