"""
This package handles and contains assets, usually strings but some binaries.
"""
import importlib
import io
import pkgutil


def getAssetAsString(fn, package="pcot.assets"):
    """Find a file in the assets package and return its contents as a string, assuming it is utf-8 encoded"""
    s = pkgutil.get_data(package, fn)
    if s is None:
        raise ValueError(f'cannot find asset {fn}')
    return s.decode('utf-8')


def getAssetAsFile(fn, package="pcot.assets"):
    """Find a file in the assets package and return it as a file-like object"""
    return io.StringIO(getAssetAsString(fn, package=package))


def getAssetPath(fn, package="pcot.assets"):
    """Find a file in the assets package and return its path"""
    with importlib.resources.path(package, fn) as p:
        return p


#
