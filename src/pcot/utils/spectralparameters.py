"""
This file deals with spectral parameters: preset expressions loaded from YAML files.
"""
import dataclasses
from pathlib import Path
from typing import Dict

import yaml



@dataclasses.dataclass
class SpectralParameter:
    """A spectral parameter"""
    expr: str   # the expression used by the SP (in PCOT expr node syntax with "a" as the image)
    desc: str   # a text description of the expression and its use


class Group:
    """a group of spectral parameters"""
    expr: str
    desc: str
    parameters: Dict[str, SpectralParameter] = dataclasses.field(default_factory=dict)

    def __init__(self, expr: str, desc: str, parameters):
        self.expr = expr
        self.desc = desc
        self.parameters = {}

        for name, parameter in parameters.items():
            self.parameters[name] = parameter


# Spectral parameters are organised into groups; each YAML file contains one group. The "builtin"
# group is loaded from the assets, while other groups can be loaded from user-provided files.

groups: Dict[str, Group] = {}

def _load_group(fn: Path):
    """Load a group from a YAML file and store it"""
    global groups
    with open(fn, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        if 'name' not in data:
            raise RuntimeError(f"No group name found in {fn}")
        if 'desc' not in data:
            raise RuntimeError(f"No group description 'desc' found in {fn}")
        if 'date' not in data:
            raise RuntimeError(f"No group date found in {fn}")
        if 'parameters' not in data:
            raise RuntimeError(f"No group parameters found in {fn}")
        if not isinstance(data['parameters'], dict):
            raise RuntimeError(f"Group parameters in {fn} must be a dictionary not {type(data['parameters'])}")
        groups[data['name']] = Group(data['name'], data['desc'], data['parameters'])



def loadSpectralParameters():
    """Load all spectral parameters from both builtins and user files."""
    from pcot.assets import getAssetPath
    _load_group(getAssetPath("builtin_spectral_parameters.yaml"))

