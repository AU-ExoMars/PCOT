"""
Handles loading ancillary data from multifile images (or "sidecar" XML files)
"""
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from pcot import ui

logger = logging.getLogger(__name__)


class MultifileSidecarLoader(ABC):
    @abstractmethod
    def attempt_load(self, path: Path, problems: List[str]) -> Optional[Dict[str, Any]]:
        """The path here is the name of the original .png or .jpg; we'll try to
        infer a path for the sidecar and load data from it. If any of that fails
        we return None and move on to the next loader - this should never raise.

        If there's no sidecar this loader recognises, just return None. If there is one
        but it can't be read (malformed, or perhaps in a different convention), also
        append a short description of the problem to 'problems' - these are only shown
        to the user if no loader manages to read the file, so that a file in another
        loader's convention doesn't produce spurious warnings."""
        pass


# this is a list of sidecar loaders - each is processed in order, and the first one
# that returns a set of data wins.
LOADERS: List[MultifileSidecarLoader] = []

def add_multifile_sidecar_loader(loader: MultifileSidecarLoader, first: bool = False):
    """Adds a multifile sidecar loader to the list of loaders. The first
    loader to successfully load data wins. Loaders are normally added to the end of
    the list, so built-in loaders (registered before plugins) are tried first. Set
    'first' to add the loader at the start instead - for example, a plugin loader for
    a newer convention which a built-in loader would also (wrongly) read successfully.
    If several loaders are added with 'first', the most recently added is tried first."""
    if loader not in LOADERS:
        if first:
            LOADERS.insert(0, loader)
        else:
            LOADERS.append(loader)


def multifile_loader(path:Path) -> Dict[str, Any]:
    """Given the path of a file being loaded into a multifile image band,
    try all the loaders to see if we can find a suitable sidecar file"""

    problems = []
    for x in LOADERS:
        try:
            data = x.attempt_load(path, problems)
        except Exception as e:
            # loaders shouldn't raise, but a buggy one (perhaps from a plugin) mustn't
            # stop the image itself from loading.
            logger.exception(f"sidecar loader {type(x).__name__} raised an exception for {path}")
            problems.append(f"{type(x).__name__}: unexpected error: {e}")
            continue
        if data is not None:
            return data

    if problems:
        ui.log(f"Could not read ancillary data for {path}: a sidecar file was found but no loader could "
               f"read it - it may be malformed, or in a convention no loader recognises yet. "
               f"Problems: {'; '.join(problems)}", loglevel=logging.WARNING)
    # otherwise return an empty dict, no extra data was found.
    return {}
