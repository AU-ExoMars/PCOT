"""
Contains types used in defining the target for calibration.
"""
from dataclasses import dataclass
from typing import Tuple

class Patch:
    """
    Base class for patches
    """
    pass

@dataclass
class CircularPatch(Patch):
    x: float  # x coordinate of centre in mm
    y: float  # y coordinate of centre in mm
    r: float  # radius in mm
    name: str  # name (e.g. "NG4")
    desc: str  # description (a colour)
    col: Tuple[float, float, float]


@dataclass
class RectPatch(Patch):
    x: float  # x coordinate of centre in mm
    y: float  # y coordinate of centre in mm
    w: float  # width in mm
    h: float  # height in mm
    name: str  # name (e.g. "NG4")
    desc: str  # description (a colour)
    col: Tuple[float, float, float]


@dataclass
class Target:
    width: float  # width in mm
    height: float  # height in mm
    # list of THREE registration points (e.g. screws in the PCT, corners in the ColorChecker)
    # Has to be three because CV's getAffineTransform takes a triangle
    regpoints: Tuple[Tuple[float, float], ...]
    instructions1: str  # instructions for the first part of setup: creating the reg. points
    instructions2: str  # instructions for part two: adjusting the reg points

    patches: Tuple[Patch, ...]  # list of patches



