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
import json
from numbers import Number
from pathlib import Path
from jinja2 import Template
from typing import List, Optional, Dict, cast, Any
import logging

from pcot.parameters.taggedaggregates import TaggedAggregate, TaggedAggregateType, Maybe, TaggedListType, \
    TaggedVariantDictType, TaggedVariantDict, TaggedList

logger = logging.getLogger(__name__)


class ApplyException(Exception):
    """An exception raised when applying a change to a tagged aggregate"""

    def __init__(self, msg):
        super().__init__(msg)


def get_element_to_modify(data: TaggedAggregate, path: List[str]):
    """Walk down the tree to the last element of the path, returning the parent of the last element.
    Remember that a path like foo.bar.baz.quux is split into root=foo, path=[bar,baz], key=quux. This
    will return the baz element - the last in the path proper, which is guaranteed to be a TaggedAggregate.

    If at any point we meet a TaggedVariantDict, we skip straight to the underlying dict. Consider the
    structure

    dict foo:
        variant dict bar:
            dict x:
                field A
                field B
            dict y

    We want to access A as "foo.bar.A" once the x has been created. That avoids the need to know the underlying
    type of the variant (we don't need to know that it's x and not y).


    """

    # surely it can't be just this??
    for p in path:
        data = data[p]
        # if we come across a TaggedVariantDict, we need to get the underlying dict
        if isinstance(data, TaggedVariantDict):
            data = data.get()
    return data


class Change:
    """The parameter file defines changes to parameters. All parameters have the following:
    * root_name: the top level of the path is the name of the tagged aggregate in the dict passed to the ParameterFile
    * path: the path to the parameter within the tagged aggregate, which is the remainder of the path passed to the ctor
    * key: the key of the parameter within the tagged aggregate, from the last element of the path
    * line: the line number in the file where the change was defined

    For example, the absolute path foo.bar.baz will be split into root_name = foo, path = [bar], key = baz.
    """

    # if we are trying to modify the root, things get weird. I'll try setting
    # the key to None
    root_name: str
    path: List[str]
    key: str
    line: int
    lineText: str  # gets filled in post-parse

    def __init__(self, path: List[str], line: int, key: str):
        if len(path) < 1:
            #            raise ValueError(f"Zero length path - are you trying to change the root?")
            self.path = []
            self.root_name = key
            self.key = None
        else:
            self.root_name, *self.path = path
            self.key = key
        self.line = line

    def show(self):
        """try to generate a string that gives the absolute path"""
        if len(self.path) > 0:
            return f"{self.root_name}.{'.'.join(self.path)}.{self.key}"
        else:
            return f"{self.root_name}.{self.key}"

    def apply(self, data: TaggedAggregate):
        pass


class SetValue(Change):
    """A change to set a value."""

    def __init__(self, path: List[str], line: int, key: str, value: str):
        super().__init__(path, line, key)
        self.value = value

    def apply(self, data: TaggedAggregate):
        logger.info(f"Setting {self.show()} to {self.value}")
        # walk down the path to get the element we want to change (well, its parent - the last item in the path)
        element = get_element_to_modify(data, self.path)
        # use the key to get its tag so we can get its type, and check it.

        try:
            tag = element.type.tag(self.key)
        except KeyError as e:
            raise KeyError(f"Cannot find {self.show()}")

        # do the actual setting, if possible - but resolve Maybe first.
        try:
            tp = tag.type
            # if the type is Maybe, check to see if we're setting it to None, and if so, set the element to None.
            if isinstance(tag.type, Maybe):
                v = self.value.lower()
                if v == 'none' or v == 'null':  # "none" and "null" are both acceptable, in upper or lowercase
                    element[self.key] = None
                    return  # return early, we're done.
                tp = tag.type.type_if_exists
            if isinstance(tp, TaggedAggregateType):
                raise ValueError(f"Cannot set a value to a tagged aggregate: {str(self)}")
            if tp is int:
                element[self.key] = int(self.value)
            elif tp is float or tag.type is Number:
                element[self.key] = float(self.value)
            elif tp is str:
                element[self.key] = self.value
            elif tp is bool:
                c = self.value.lower()[0]
                element[self.key] = (c == 't') or (c == 'y')  # just check the first character, upper or lower
            else:
                raise ValueError(f"unparameterisable {tag.type} for {str(self)}")
        except ValueError as e:
            raise ValueError(f"{str(self)}: expected {tag.type}, got {type(self.value)} ({self.value})") from e

    def __repr__(self):
        return f"SetValue({self.line}, root={self.root_name} path={'.'.join(self.path)} key={self.key}) val={self.value}"


class DeleteValue(Change):
    """A change to delete a value."""

    def __init__(self, path: List[str], line: int, key: str):
        super().__init__(path, line, key)

    def apply(self, data: TaggedAggregate):
        logger.info(f"Deleting {self.path + [self.key]}")
        raise NotImplementedError(repr(self))

    def __repr__(self):
        return f"DeleteValue({self.line}, root={self.root_name} path={'.'.join(self.path)} key={self.key})"


class AddToNonListException(ValueError):
    def __init__(self, add: 'Add', elem):
        msg = \
            f"Cannot append to a non-list: {'.'.join(add.path)} is a {type(elem).__name__}"
        super().__init__(msg)


class Add(Change):
    """Add to the list at the given path+key. It may be that we are adding to a list of variant dicts, in
    which case we should specify the type of the variant."""

    def __init__(self, path: List[str], line: int, key: str, variant: Optional[str] = None):
        super().__init__(path, line, key)
        if variant == '':  # in typical usage the variant is an empty string!
            variant = None
        self.variant = variant

    def __repr__(self):
        if self.variant is not None:
            return f"Add({self.line}, root={self.root_name} path={'.'.join(self.path)} key={self.key} variant={self.variant})"
        else:
            return f"Add({self.line}, root={self.root_name} path={'.'.join(self.path)} key={self.key})"

    def apply(self, data: TaggedAggregate):
        logger.info(f"Adding to {self.path + [self.key]}")
        # then get the tag for the item we want to append to. If the key is
        # None, we're trying to append to a list at the root.
        if self.key is None:
            # In that case, we need to do things differently because the tag in the list
            # applies to the members of the list. We can't check the that the item is a list
            # itself the same way as we do in the more common 'else' clause, because we don't
            # have a tag for it (it's the root, not part of a TaggedAggregate).
            if not isinstance(data.type, TaggedListType):
                raise ValueError(f"Cannot add to a non-list: {str(self)}")
            type_of_items = data.type.tag().type
            list_to_append_to = cast(TaggedList, data)
        else:
            # otherwise we can get a tag for the list from the parent.
            # check it's a list - we get the parent of the item we want to append to
            element_containing_the_list = get_element_to_modify(data, self.path)
            if not isinstance(element_containing_the_list, TaggedAggregate):
                raise AddToNonListException(self, element_containing_the_list)
            # now we can get the type of the item we want to append to (which should be a TaggedList)
            tag = element_containing_the_list.type.tag(self.key)
            # and check its type (it should be a list). "Maybe" checking is a bit messy here.
            # We also get the type of the items in the list. The tag has a TaggedListType object (tag.type)
            # which itself will have a tag, which will have a type (the type of the items).
            if isinstance(tag.type, Maybe):
                if not isinstance(tag.type.type_if_exists, TaggedListType):
                    raise AddToNonListException(self, tag.type.type_if_exists)
                type_of_items = tag.type.type_if_exists.tag().type
            elif isinstance(tag.type, TaggedListType):
                type_of_items = tag.type.tag().type
            else:
                raise AddToNonListException(self, tag.type)
            list_to_append_to = element_containing_the_list[self.key]
        if self.variant is not None:  # a variant has been specified (e.g. "foo+bar" in a path)
            # are we dealing with a list of variant dicts?
            if not isinstance(type_of_items, TaggedVariantDictType):
                raise ValueError(
                    f"specifying a variant when adding to a non-variant list (e.g. foo+bar) is invalid: {str(self)}")
            # we are. Check that the variant is valid in this list.
            if self.variant not in type_of_items.type_dict:
                poss = ",".join(type_of_items.type_dict.keys())
                raise ValueError(
                    f"{self.variant} is not a valid variant for adding to this list. Possibilities are: {poss}")
            # it's valid, so we should be able to make one.
            underlying_dict = type_of_items.type_dict[self.variant].create()  # will create the underlying dict
            # now create the containing variant dict and set it to contain that item
            variant_dict_item = type_of_items.create().set(underlying_dict)
            # and append
            list_to_append_to.append(variant_dict_item)
        else:
            if list_to_append_to is None:
                raise ValueError(f"Cannot add to a null list: {str(self)}")
            list_to_append_to.append_default()


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

    def load(self, path: Path, template_data: Optional[Dict[str, Any]]=None) -> 'ParameterFile':
        """Load a parameter file from a path, returns self for fluent use. The parameter file will
        also be run through Jinja2 templating with the data passed in."""
        self.path = str(path)
        logger.info(f"Processing parameter file {self.path}")
        with open(path, 'r') as f:
            s = f.read()
            self.parse(s, template_data or {})
        return self

    def parse(self, ss, template_data: Optional[Dict[str, Any]]=None) -> 'ParameterFile':
        """Load a parameter file from a string, returns self for fluent use. We also process
        the parameter file as a Jinja2 template"""

        template = Template(ss)     # read in the parameter file and create a Jinja template from it
        ss = template.render(template_data)  # render the template with the data passed in

        lines = ss.split('\n')
        for i, line in enumerate(lines):
            # remove comments - anything after the final '#'
            if '#' in line:
                line = line[:line.index('#')]
            # clean up the line
            line = line.strip()
            # skip empty lines
            if not line:
                continue
            self._parse(line, i)
        for c in self._changes:
            c.lineText = lines[c.line]
        return self

    def apply(self, data: Dict[str, TaggedAggregate]):
        """Try to apply the changes to some data objects. Firstly, we look up the tagged aggregate using the first
        element of the path. If it doesn't exist, we abort silently. Otherwise we use the rest of the path to reference
        data within the aggregate and change it."""

        for c in self._changes:
            if c.root_name in data:
                try:
                    c.apply(data[c.root_name])
                except Exception as e:
                    raise ApplyException(
                        f"Error applying change line {c.line}: {c.lineText}, change is {c}. Error: {e} ") from e

    def _parse(self, line: str, lineNo: int = 0):
        """Process each line, adding Change objects to the list of changes if required"""
        logger.info(f"Processing line {lineNo}: {line}")
        if '=' in line:
            parts = [x.strip() for x in line.split('=', 1)]
            path, key = self._parse_path(lineNo, parts[0], False)  # may append an Add change
            # this is where the processing has to get a bit weird. We take the value, and if it begins
            # and ends with a quote we assume it's a JSON-serialisable value and decode it. That lets us
            # put whitespace and escaped characters in it.
            v = parts[1]
            if v.strip()[0] == '"' and v.strip()[-1] == '"':
                v = json.loads(v)
            self._changes.append(SetValue(path, lineNo, key, v))
        elif line.startswith('del'):
            line = line[3:].strip()
            path, key = self._parse_path(lineNo, line)  # may append an Add change
            self._changes.append(DeleteValue(path, lineNo, key))
        else:
            # don't create a change, we're just changing the path
            self._parse_path(lineNo, line, True)

    def _parse_path(self, lineNo: int, path_string: str, is_path_only: bool = False) -> (List[str], str):
        """Set the path and key from a path string - this is the bit before the equals sign. The path
        is (if you like) the "directory" of the parameter, the key is the individual parameter name.
        For example "foo.bar.baz" would set the path to ["foo", "bar"] and the key to "baz". Then returns
        the current path (or a copy thereof) and the key so we can create a Change if required.
        May also create some Changes itself - such as Adds, which indicate a new item should be created in
        a list.
        """
        # it is divided into parts by dots. The last dot indicates the end of the path, and after the last dot
        # is the key we want to set.
        elements = [x.strip() for x in path_string.split('.')]

        # preprocessing - any element that ends in [xxxx] is an index, and should be split into two elements, so
        # x[y] becomes two elements x,y. These needs to work on multidimensional arrays too, so x[y][z] becomes
        # x,y,z.
        path = []  # this is the path we are building by preprocessing the elements to handle indices
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
                # and set can just set the current path from the path we read,
                self._path = path
            else:
                # The path is relative. If there is just one empty element, that doesn't change the path - we're working
                # at the same level. For each extra empty element, we go up one level - at each level ensuring that
                # we haven't run out of elements.

                if len(self._path) == 0:
                    raise ValueError(f"Invalid parameter path: {path_string} - relative path not valid here.")
                prev_path = self._path.copy()
                # pop empty elements off the start of the path until we hit a non-empty element.
                empty_ct = 0
                while len(path) > 0 and path[0] == '':
                    path.pop(0)
                    empty_ct += 1
                # ensure there are no empty elements in the rest of the path.
                if '' in path:
                    raise ValueError(
                        f"Invalid parameter path: {path_string} - relative path must not contain empty elements after the "
                        f"first.")
                # now pop the same number of elements off the current path (less one!), making sure there are enough
                pop_count = empty_ct - 1
                if pop_count > len(self._path):
                    raise ValueError(
                        f"Invalid parameter path: {path_string} - relative path goes too high for path {prev_path}.")
                if pop_count > 0:
                    self._path = self._path[:-pop_count]
                # remaining items in path are appended to the current path.
                self._path.extend(path)

        # now we post-process the path to handle "+" symbols. This will create Add changes.
        self._process_adds_in_path(lineNo)

        # we'll have to handle the key separately, which may also have a "+". In that case we
        # convert (say) a.b.+ into a.b.-1, and create an Add change for a.b.
        if "+" in key:
            if key[0] != '+':
                raise ValueError(f"Invalid path element {key} in {self._path}")
            # strip the +
            variant = key[1:]
            # create the add for that
            p = self._path.copy()
            # if we have (say) a.b.c.+, we want to do the add at a.b key c.
            self._changes.append(Add(p[:-1], lineNo, p[-1], variant))
            if is_path_only:
                # if we're just a path setter, we add -1 to the path so that subsequent relative paths
                # will be relative to the item we just added.
                self._path.append('-1')
                key = ''
            else:
                # and set the key to -1 for returning; the SetValue will modify the item added to the list
                key = '-1'

        logger.info(f"path now is {self._path}, key is {key}")
        return self._path.copy(), key  # return a copy of the path, not the path itself.

    def _process_adds_in_path(self, lineNo: int):
        """Run through the elements of the path looking for "+" symbols. If we find one, we create an Add change
        for that point in the path. This is used to add a new item to a list.
        Consider the path
            foo.bar.+.baz
        This should become
            foo.bar.-1.baz
        with an Add change created for foo.bar executed before the SetValue for foo.bar.-1.baz.
        """
        for i, p in enumerate(self._path):
            if "+" in p:
                if p[0] != '+':
                    # if it's not at the beginning it's not valid
                    raise ValueError(f"Invalid path element {p} in {self._path}")
                # anything after the + indicates we're adding a variant dict and what the
                # type of the variant is.
                variant = p[1:]
                # create a new change to add an element to the list at this point
                # In the case of "foo.bar.+.baz" we need to add the new element at path=foo, key=bar.
                self._changes.append(Add(self._path[:i - 1], lineNo, self._path[i - 1], variant))  # path, line-no, key
                # replace the + with -1 (we're adding at the end, so we're now setting
                # data in the new last element)
                self._path[i] = '-1'

    def __str__(self):
        return f"{self.path}: {len(self._changes)} changes"

    def __repr__(self):
        return f"ParameterFile({self.path})"

    def dump(self):
        print(f"Parameter file {self.path}")
        for c in self._changes:
            print(repr(c))


if __name__ == "__main__":
    # read a line from console
    ln = 0
    p = ParameterFile()
    while True:
        s = input("enter a parameter file line:")
        if s == 'quit':
            break
        if s == 'clr':
            p = ParameterFile()
            ln = 0
            continue
        p._parse(s, ln)
        ln += 1
        print("---------------------------------" + s)
        for x in p._changes:
            print(x)
