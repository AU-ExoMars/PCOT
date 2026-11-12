"""
This file deals with spectral parameters: preset expressions loaded from YAML files.
"""
import dataclasses
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from pcot.datum import Datum
from pcot.expressions.eval import ExpressionEvaluator, unboundVar
from pcot.expressions.parse import CompiledExpression

logger = logging.getLogger(__name__)

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

    def run(self, d: Datum) -> Datum:
        """Run the spectral parameter on a datum, which must be an image"""
        if not isinstance(d, Datum):
            raise TypeError(f"Expected Datum but got {type(d)} in parameter {self.name}")
        if d.tp != Datum.IMG:
            raise TypeError(f"Expected an image but got {d.tp.name} in parameter {self.name}")
        return _spectralEvaluator.run(self.compiled, {"a": d})




class Group:
    """a group of spectral parameters"""
    expr: str
    desc: str
    parameters: Dict[str, SpectralParameter]
    path: Path

    def __init__(self, expr: str, desc: str, parameters, path: Path):
        """Parse a dict into a Group object."""
        self.expr = expr
        self.desc = desc
        self.parameters = {}
        self.path = path

        for name, parameter in parameters.items():
            self.parameters[name] = SpectralParameter(name, parameter)

    def keys(self):
        return self.parameters.keys()
    def values(self):
        return self.parameters.values()
    def items(self):
        return self.parameters.items()

    def __getitem__(self, key):
        return self.parameters[key]


# Spectral parameters are organised into groups; each YAML file can contain multiple groups.
# The builtins groups are loaded from the assets, while other groups can be loaded from user-provided files.

groups: Dict[str, Group] = {}

def _load_groups(fn: Path):
    """Load the groups from a YAML file and store them. Raises an exception if anything is wrong with the
    file, in which case none of the groups in that file are stored."""
    global groups
    with open(fn, "r") as f:
        file = yaml.load(f, Loader=yaml.SafeLoader)
    if not isinstance(file, dict):
        raise ValueError(f"Spectral parameter file {fn} must be a dictionary of groups")

    # build the new groups separately, so that a file with an error in it doesn't get partially loaded.
    newgroups = {}
    logger.debug(f"Loading groups from {fn}")
    for name, data in file.items():
        logger.debug(f"Loading group {name}")
        if not isinstance(data, dict):
            raise ValueError(f"Group {name} in {fn} must be a dictionary not {type(data)}")
        if 'desc' not in data:
            raise AttributeError(f"No group description 'desc' found in {fn}")
        if 'date' not in data:
            raise AttributeError(f"No group date found in {fn}")
        if 'parameters' not in data:
            raise AttributeError(f"No group parameters found in {fn}")
        if not isinstance(data['parameters'], dict):
            raise ValueError(f"Group parameters in {fn} must be a dictionary not {type(data['parameters'])}")
        if name in groups:
            g = groups[name]
            raise AttributeError(f"Spectral parameter group {name} already exists in {g.path}, cannot define again in {fn}")
        newgroups[name] = Group(name, data['desc'], data['parameters'], fn)
    groups.update(newgroups)


class _Errors:
    """Handles a list of errors, crudely encapsulated"""
    _errors: List[Tuple[str, str]]  # ("warn" or "error", text)

    def __init__(self):
        self._errors = []

    def clear(self):
        self._errors = []

    def _add_error(self, error: str):
        self._errors.append(("error", error))
    def _add_warning(self, warning: str):
        self._errors.append(("warn", warning))

    def __iter__(self):
        return iter(self._errors)

errors = _Errors()


def loadSpectralParameters():
    """Load all spectral parameters from both builtins and user files."""
    from pcot.assets import getAssetPath
    from pcot.config import data

    # we have to initialise the expression evaluator - it's done here so we can make sure
    # all plugins etc. are loaded first.

    global _spectralEvaluator
    _spectralEvaluator = ExpressionEvaluator()

    # start from scratch, so that calling this again (e.g. pcot.setup() being called more than once)
    # reloads everything rather than failing because the builtin groups already exist.
    groups.clear()
    errors.clear()

    # load builtins first - errors here are fatal.
    _load_groups(getAssetPath("data/builtin_spectral_parameters.yaml"))
    # then user data. Missing files are skipped and files with errors are reported and ignored,
    # so that a bad entry in the config can't stop PCOT starting.
    for x in data.locations.userspecparams:
        if not Path(x).is_file():
            e = f"User spectral parameter file {x} not found, skipping"
            logger.warning(e)
            errors._add_warning(e)
            continue
        try:
            _load_groups(x)
        except Exception as e:
            e = f"Cannot load user spectral parameter file {x}, ignoring it: {e}"
            logger.error(e)
            errors._add_error(e)
