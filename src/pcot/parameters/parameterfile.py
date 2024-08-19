"""
This module handles parameter files - ways of changing multiple parameters, which are stored as TaggedAggregate
objects.

The workflow is as follows:

* load a parameter file from a path (or string if we are testing)
* parse the file into a list of changes
* add a set of tagged aggregates to a dictionary
* run the "apply" method of the parameter file using that dictionary

This will apply the changes to the tagged aggregates which are in the dictionary - the first element of the
path is used to look up the TA in the dict, and the rest of the path is used to find the parameter within the TA.

Quite often there will only be a single TA in the dict. We load a single parameter file, and then run every node
in the graph through it as we load them, with just that node in the dictionary.
"""
from numbers import Number
from pathlib import Path
from typing import List, Optional, Dict
import logging

from pcot.parameters.taggedaggregates import TaggedAggregate, TaggedAggregateType, Maybe

logger = logging.getLogger(__name__)


def get_element_to_modify(data: TaggedAggregate, path: List[str]):
    """Walk down the tree to the last element of the path, returning the parent and the key of the last element"""

    # surely it can't be just this??
    for p in path:
        data = data[p]
    return data


class Change:
    """The parameter file defines changes to parameters. All parameters have the following:
    * root_name: the top level of the path is the name of the tagged aggregate in the dict passed to the ParameterFile
    * path: the path to the parameter within the tagged aggregate, which is the remainder of the path passed to the ctor
    * key: the key of the parameter within the tagged aggregate, from the last element of the path
    * line: the line number in the file where the change was defined

    For example, the absolute path foo.bar.baz will be split into root_name = foo, path = [bar], key = baz.
    """

    root_name: str
    path: List[str]
    key: str
    line: int

    def __init__(self, path: List[str], line: int, key: str):
        self.root_name, *self.path = path
        self.key = key
        self.line = line

    def apply(self, data: TaggedAggregate):
        pass


class SetValue(Change):
    """A change to set a value."""

    def __init__(self, path: List[str], line: int, key: str, value: str):
        super().__init__(path, line, key)
        self.value = value

    def apply(self, data: TaggedAggregate):
        logger.info(f"Setting {self.path + [self.key]} to {self.value}")
        # walk down the path to get the element we want to change
        element = get_element_to_modify(data, self.path)
        # get its tag so we can get its type, and check it.
        tag = element._type.tag(self.key)

        # do the actual setting, if possible - but resolve Maybe first.
        try:
            tp = tag.type
            # if the type is Maybe, check to see if we're setting it to None, and if so, set the element to None.
            if isinstance(tag.type, Maybe):
                v = self.value.lower()
                if v == 'none' or v == 'null':          # "none" and "null" are both acceptable, in upper or lowercase
                    element[self.key] = None
                    return  # return early, we're done.
                tp = tag.type.tp
            if isinstance(tp, TaggedAggregateType):
                raise ValueError(f"Cannot set a value to a tagged aggregate: {str(self)}")
            if tp is int:
                element[self.key] = int(self.value)
            elif tp is float or tag.type is Number:
                element[self.key] = float(self.value)
            elif tp is str:
                element[self.key] = self.value
            elif tp is bool:
                element[self.key] = self.value.lower()[0] == 't'    # just check the first character, upper or lower
            else:
                raise ValueError(f"unparameterisable {tag.type} for {str(self)}")
        except ValueError as e:
            raise ValueError(f"{str(self)}: could not set {self.value} as a {tag.type}") from e

    def __str__(self):
        return f"line {self.line}: {'.'.join(self.path)}.{self.key} = {self.value}"

    def __repr__(self):
        return f"SetValue({self.line}, {'.'.join(self.path)}, {self.key}, {self.value})"


class DeleteValue(Change):
    """A change to delete a value."""

    def __init__(self, path: List[str], line: int, key: str):
        super().__init__(path, line, key)

    def apply(self, data: TaggedAggregate):
        logger.info(f"Deleting {self.path + [self.key]}")

    def __repr__(self):
        return f"DeleteValue({self.line}, {'.'.join(self.path)}, {self.key})"


class ParameterFile:
    """Represents a parameter file: a set of changes which can be applied to a graph as it is loaded.
    This class knows nothing about TaggedAggregates, it just deals with the file format."""

    _path: List[str]  # the path to the parent of the last parameter we set
    _changes: List[Change]  # the changes to be applied
    path: str  # either the path to the file or "(no path)"

    def __init__(self):
        """Create the parameter file object - then use either load (for files) or parse (for strings) to read it"""
        self._path = []
        self._changes = []
        self.path = "(no path)"

    def load(self, path: Path) -> 'ParameterFile':
        """Load a parameter file from a path, returns self for fluent use"""
        self.path = str(path)
        logger.info(f"Processing parameter file {self.path}")
        with open(path, 'r') as f:
            s = f.read()
            self.parse(s)
        return self

    def parse(self, ss) -> 'ParameterFile':
        """Load a parameter file from a string, returns self for fluent use"""
        for i, line in enumerate(ss.split('\n')):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            c = self._process(line, i)
            if c:
                self._changes.append(c)
        return self

    def _process_path(self, path_string: str):
        """Set the path and key from a path string - this is the bit before the equals sign. The path
        is (if you like) the "directory" of the parameter, the key is the individual parameter name.
        For example "foo.bar.baz" would set the path to ["foo", "bar"] and the key to "baz".
        """
        # it is divided into parts by dots. The last dot indicates the end of the path, and after the last dot
        # is the key we want to set.
        elements = [x.strip() for x in path_string.split('.')]

        # preprocessing - any element that ends in [xxxx] is an index, and should be split into two elements, so
        # x[y] becomes two elements x,y. These needs to work on multidimensional arrays too, so x[y][z] becomes
        # x,y,z.
        path = []           # this is the path we are building by preprocessing the elements to handle indices
        for s in elements:
            if '[' in s:
                # split the string into parts - so foo[bar] becomes foo,bar] and foo[bar][baz] becomes foo,bar],baz]
                parts = s.split('[')
                # the first part just gets added
                path.append(parts[0])
                # the rest of the parts get added as separate elements, with the trailing bracket removed
                for p in parts[1:]:
                    path.append(p[:-1])
            else:
                path.append(s)

        if len(path) == 1:
            # there is no dot, so this is a top-level parameter: the path will be empty.
            key = path_string
            self._path = []
        else:
            # the last element is the key, the rest is the path.
            key = path.pop()
            # We may be dealing with a relative path, if the first element is the empty string.
            if path[0] != '':
                # If the path is absolute, no other element should be empty.
                if '' in path[1:]:
                    raise ValueError(
                        f"Invalid parameter: {path_string} - an absolute path must not contain empty elements.")
                # and set can just set the current path from the path we read.
                self._path = path
            else:
                # The path is relative. If there is just one empty element, that doesn't change the path - we're working
                # at the same level. For each extra empty element, we go up one level - at each level ensuring that
                # we haven't run out of elements.
                prev_path = self._path.copy()
                # pop empty elements off the start of the path until we hit a non-empty element.
                empty_ct = 0
                while len(path) > 0 and path[0] == '':
                    path.pop(0)
                    empty_ct += 1
                # ensure there are no empty elements in the rest of the path.
                if '' in path:
                    raise ValueError(
                        f"Invalid parameter: {path_string} - relative path must not contain empty elements after the "
                        f"first.")
                # now pop the same number of elements off the current path (less one!), making sure there are enough
                pop_count = empty_ct - 1
                if pop_count > len(self._path):
                    raise ValueError(
                        f"Invalid parameter: {path_string} - relative path goes too high for path {prev_path}.")
                if pop_count > 0:
                    self._path = self._path[:-pop_count]
                # remaining items in path are appended to the current path.
                self._path.extend(path)
        logger.info(f"path now is {self._path}, key is {key}")
        return self._path.copy(), key  # return a copy of the path, not the path itself.

    def _process(self, line: str, lineNo: int = 0) -> Optional[Change]:
        """Process each line, generating a Change of some kind"""
        if '=' in line:
            parts = [x.strip() for x in line.split('=')]
            path, key = self._process_path(parts[0])
            return SetValue(path, lineNo, key, parts[1])
        elif line.startswith('del'):
            line = line[3:].strip()
            path, key = self._process_path(line)
            return DeleteValue(path, lineNo, key)
        else:
            # don't create a change, we're just changing the path
            self._path, key = self._process_path(line)
            return None

    def apply(self, data: Dict[str, TaggedAggregate]):
        """Try to apply the changes to some data objects. Firstly, we look up the tagged aggregate using the first
        element of the path. If it doesn't exist, we abort silently. Otherwise we use the rest of the path to reference
        data within the aggregate and change it."""

        for c in self._changes:
            if c.root_name in data:
                c.apply(data[c.root_name])

    def __str__(self):
        return f"{self.path}: {len(self._changes)} changes"

    def __repr__(self):
        return f"ParameterFile({self.path})"
