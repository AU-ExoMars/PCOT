"""
This package deals with camera data: filters, flatfield data and so on.
It also deals with reflectance target data.
"""
import logging
import os.path
from pathlib import Path
from typing import Set, List

from pcot.cameras.reflectances import Reflectance

logger = logging.getLogger(__name__)

# dictionary of CameraData
_cameras = dict()
# dictionary of reflectances
_reflectances = dict()

class CameraNotFoundException(Exception):
    name: str
    def __init__(self, name):
        super().__init__(f"Camera not found: {name}")
        self.name = name

class ReflectanceNotFoundException(Exception):
    name: str
    def __init__(self, name):
        super().__init__(f"Reflectance target not found: {name}")
        self.name = name
        


def getCamera(name: str) -> 'CameraData':
    """Get the CameraData object for the given camera name"""
    if name not in _cameras:
        raise CameraNotFoundException(name)
    return _cameras[name]


def getCameraNames() -> List[str]:
    """Return a list of the names of all the cameras"""
    return sorted(_cameras.keys())


def loadAllCameras(path: str):
    """Load all the camera data files in the given directory"""
    import glob
    global _cameras
    from pcot.cameras.camdata import CameraData
    path = os.path.expanduser(path)
    logger.debug(f"Loading camera data from {path}")
    for file in glob.glob(path + "/*.parc"):
        logger.debug(f"Loading camera data from {file}")
        data = CameraData(file)
        # this is where having a TaggedDict called "params" *inside* the CameraParams object is a bit grim.
        _cameras[data.params.params.name] = data
        logger.info(f"Loaded camera {data.params.params.name} from {file}")


def getFilter(cameraName, target, search='name'):
    cam = getCamera(cameraName)
    return cam.getFilter(target, search=search)


def getReflectance(name: str) -> Reflectance:
    """Get the object for the given reflectance target name"""
    if name not in _reflectances:
        raise ReflectanceNotFoundException(name)
    return _reflectances[name]


def getReflectanceNames() -> List[str]:
    """Return a list of the names of all the reflectance targets"""
    return sorted(_reflectances.keys())


def loadAllReflectances(path: str):
    """Load all the camera data files in the given directory"""
    import glob
    global _reflectances
    from pcot.cameras import reflectances
    path = os.path.expanduser(path)
    logger.debug(f"Loading reflectance data from {path}")
    for file in glob.glob(path + "/*.parc"):
        logger.debug(f"Loading reflectance data from {file}")
        data = reflectances.load(Path(file))
        # this is where having a TaggedDict called "params" *inside* the CameraParams object is a bit grim.
        _reflectances[data.metadata.name] = data
        logger.info(f"Loaded camera {data.metadata.name} from {file}")
