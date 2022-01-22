"""Common tools for (ExoMars) data product processing software.
"""

try:
    import importlib.metadata as importlib_metadata  # type: ignore
except ImportError:
    import importlib_metadata
_dist_meta = importlib_metadata.metadata("proctools")
__author__ = _dist_meta["Author"]
__description__ = _dist_meta["Summary"]
__project__ = _dist_meta["Name"]
__url__ = _dist_meta["Home-Page"]
__version__ = _dist_meta["Version"]
del _dist_meta
