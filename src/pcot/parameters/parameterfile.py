from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Change:
    """The parameter file defines changes to parameters."""

    def __init__(self, path: List[str], line: int, key: str):
        self.path = path
        self.key = key
        self.line = line

    def apply(self):
        pass


class SetValue(Change):
    """A change to set a value."""

    def __init__(self, path: List[str], line: int, key: str, value: str):
        super().__init__(path, line, key)
        self.value = value

    def apply(self):
        logger.info(f"Setting {self.path + [self.key]} to {self.value}")

    def __repr__(self):
        return f"SetValue({self.line}, {'.'.join(self.path)}, {self.key}, {self.value})"


class DeleteValue(Change):
    """A change to delete a value."""

    def __init__(self, path: List[str], line: int, key: str):
        super().__init__(path, line, key)

    def apply(self):
        logger.info(f"Deleting {self.path + [self.key]}")

    def __repr__(self):
        return f"DeleteValue({self.line}, {'.'.join(self.path)}, {self.key})"


class ParameterFile:
    """Represents a parameter file: a set of changes which can be applied to a graph as it is loaded.
    This class knows nothing about TaggedAggregates, it just deals with the file format."""

    _current: List[str]  # the path to the parent of the last parameter we set
    _changes: List[Change]  # the changes to be applied
    path: str  # either the path to the file or "(no path)"

    def __init__(self):
        """Create the parameter file object - then use either load (for files) or parse (for strings) to read it"""
        self._current = []
        self._changes = []
        self.path = "(no path)"

    def load(self, path: Path) -> 'ParameterFile':
        """Load a parameter file from a path, returns self for fluent use"""
        self.path = str(path)
        logger.info(f"Processing parameter file {self.path}")
        with open(path, 'r') as f:
            s = f.readlines()
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
        # x[y] becomes two elements x,y. These needs to work on multidimension arrays too, so x[y][z] becomes
        # x,y,z.
        path = []
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
            path = []
            key = path_string
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
                self._current = path
            else:
                # The path is relative. If there is just one empty element, that doesn't change the path - we're working
                # at the same level. For each extra empty element, we go up one level - at each level ensuring that
                # we haven't run out of elements.
                prevCurrent = self._current.copy()
                # pop empty elements off the start of the path until we hit a non-empty element.
                empty_ct = 0
                while len(path) > 0 and path[0] == '':
                    path.pop(0)
                    empty_ct += 1
                # ensure there are no empty elements in the rest of the path.
                if '' in path:
                    raise ValueError(
                        f"Invalid parameter: {path_string} - relative path must not contain empty elements after the first.")
                # now pop the same number of elements off the current path (less one!), making sure there are enough
                pop_count = empty_ct - 1
                if pop_count > len(self._current):
                    raise ValueError(
                        f"Invalid parameter: {path_string} - relative path goes too high for path {prevCurrent}.")
                if pop_count > 0:
                    self._current = self._current[:-pop_count]
                # remaining items in path are appended to the current path.
                self._current.extend(path)
        logger.info(f"path now is {self._current}, key is {key}")
        return self._current.copy(), key  # return a copy of the path, not the path itself.

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
            self._current, key = self._process_path(line)
            return None

    def __str__(self):
        return f"{self.path}: {len(self._changes)} changes"

    def __repr__(self):
        return f"ParameterFile({self.path})"
