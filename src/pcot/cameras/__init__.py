"""
This package deals with camera data: filters, flatfield data and so on.
"""
import logging
import os.path
from typing import Set, List

logger = logging.getLogger(__name__)

# dictionary of CameraData
_cameras = dict()


def getCamera(name: str) -> 'CameraData':
    """Get the CameraData object for the given camera name"""
    if name not in _cameras:
        raise ValueError(f"Camera {name} not found")
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
