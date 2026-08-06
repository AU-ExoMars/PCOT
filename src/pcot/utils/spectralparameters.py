"""
This file deals with spectral parameters: preset expressions loaded from YAML files.
"""
from pathlib import Path
from typing import Dict

import yaml

from pcot.expressions.eval import ExpressionEvaluator, unboundVar
from pcot.expressions.parse import CompiledExpression

# this is the evaluator that SpectralParameters will use; it's private to this module.
# We don't create it until late in setup, when all the plugins etc. are loaded.

_spectralEvaluator:ExpressionEvaluator

class SpectralParameter:
    """A spectral parameter"""
    name: str   # name of the parameter for error reporting and debugging
    expr: str   # the expression used by the SP (in PCOT expr node syntax with "a" as the image)
    desc: str   # a text description of the expression and its use
    compiled: CompiledExpression    # the expression in compiled form

    def setExpression(self,expr:str):
        """Compile the expression"""
        self.expr = expr
        try:
            self.compiled = _spectralEvaluator.compile(expr,{"a": unboundVar})
        except Exception as e:
            raise Exception(f"error compiling spectral parameter '{self.name}': {e}") from e

    def __init__(self, name: str, d: Dict):
        """Parse a dict into a SpectralParameter object"""
        self.name = name
        if not isinstance(d, Dict):
            raise TypeError(f"Expected dict but got {type(d)} in parameter {name}")

        if "expr" not in d:
            raise AttributeError(f"SpectralParameter requires 'expr' key in parameter {name}")
        self.setExpression(d['expr'])

        if "desc" not in d:
            raise AttributeError(f"SpectralParameter requires 'desc' key in parameter {name}")
        self.desc = d['desc']



class Group:
    """a group of spectral parameters"""
    expr: str
    desc: str
    parameters: Dict[str, SpectralParameter]

    def __init__(self, expr: str, desc: str, parameters):
        """Parse a dict into a Group object."""
        self.expr = expr
        self.desc = desc
        self.parameters = {}

        for name, parameter in parameters.items():
            print(parameter)
            self.parameters[name] = SpectralParameter(name, parameter)

    def keys(self):
        return self.parameters.keys()
    def values(self):
        return self.parameters.values()
    def items(self):
        return self.parameters.items()


# Spectral parameters are organised into groups; each YAML file contains one group. The "builtin"
# group is loaded from the assets, while other groups can be loaded from user-provided files.

groups: Dict[str, Group] = {}

def _load_group(fn: Path):
    """Load a group from a YAML file and store it"""
    global groups
    with open(fn, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        if 'name' not in data:
            raise AttributeError(f"No group name found in {fn}")
        if 'desc' not in data:
            raise AttributeError(f"No group description 'desc' found in {fn}")
        if 'date' not in data:
            raise AttributeError(f"No group date found in {fn}")
        if 'parameters' not in data:
            raise AttributeError(f"No group parameters found in {fn}")
        if not isinstance(data['parameters'], dict):
            raise ValueError(f"Group parameters in {fn} must be a dictionary not {type(data['parameters'])}")
        groups[data['name']] = Group(data['name'], data['desc'], data['parameters'])



def loadSpectralParameters():
    """Load all spectral parameters from both builtins and user files."""
    from pcot.assets import getAssetPath

    # we have to initialise the expression evaluator - it's done here so we can make sure
    # all plugins etc. are loaded first.

    global _spectralEvaluator
    _spectralEvaluator = ExpressionEvaluator()

    _load_group(getAssetPath("builtin_spectral_parameters.yaml"))

