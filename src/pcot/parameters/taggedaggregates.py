import dataclasses
from abc import ABC, abstractmethod
from copy import copy
from numbers import Number
from typing import Any, Dict, Union, List, Tuple, Optional

import numpy as np


class Maybe:
    """Objects of this class wrap both type objects ('int' etc.) and TaggedAggregateType objects, to indicate that
    this is optional in a type hint. We can't use Optional because it woon't work with TaggedAggregateType objects

    We did have an Amalgam object, but that can't possibly work because we don't actually store type data in
    the serialisation so we can't tell what to deserialise to. Maybe only works because we can check for None.
    """

    type_if_exists: Any

    def __init__(self, tp):
        self.type_if_exists = tp

    def __repr__(self):
        return f"Maybe({self.type_if_exists})"


def is_value_of_type(value, tp):
    """Type checker that is aware of "Maybe"
    This doesn't do what check_type inside the constructors do - that checks that the type is OK, this checks
    that a value matches a type."""
    if isinstance(tp, Maybe):
        # check the value is None or of the correct type
        return value is None or is_value_of_type(value, tp.type_if_exists)
    if tp is type(None):  # NoneType isn't available anywhere, but there's only one None and one NoneType
        return value is None
    if isinstance(tp, TaggedAggregateType):
        # are we expecting a tagged aggregate?
        if isinstance(value, TaggedAggregate):
            # it's a tagged agg, but not the right type.
            return tp == value.type
        else:
            # we're expecting a tagged agg and we haven't got one.
            return False

    return isinstance(value, tp)


class TaggedAggregateType(ABC):
    """This is the base class for tagged aggregate type objects. These define what types the values in the aggregate
    should have. Each TaggedAggregate has a ref to one of these *of the appropriate type*, so a TaggedDict will have
    a TaggedDictType, etc."""

    @abstractmethod
    def create(self):
        """Create a the appropriate default values"""
        raise NotImplementedError("createDefaults not implemented")

    @abstractmethod
    def deserialise(self, data):
        """Deserialise the type from a JSON-serialisable structure, returning a new instance of the appropriate
        TaggedAggregate"""
        raise NotImplementedError("deserialise not implemented")


class TaggedAggregate(ABC):
    """This is the base class for tagged aggregate objects. These are the actual objects that hold the values.
    Each has an appropriate TaggedAggregateType object that defines the types of the values. The reference to
    the type is here, not in the subtype, although the subtype limits what the actual type can be. This is to
    make it easier to check we have the correct type."""
    _type: TaggedAggregateType  # will always be the appropriate subtype of TaggedAggregateType

    def __init__(self, tp: TaggedAggregateType):
        self._type = tp

    @property
    def type(self):
        """Return the type of this object"""
        return self._type

    @abstractmethod
    def serialise(self):
        """Serialise the type into a JSON-serialisable structure"""
        raise NotImplementedError("serialise not implemented")


@dataclasses.dataclass
class Tag:
    """This is the class that holds the information for each tag."""
    description: str
    type: Union[type, TaggedAggregateType]  # either a type or one of the TaggedAggregateType objects
    deflt: Any = None  # the default value is ignored (and none) if the type is a TaggedAggregateType

    def assert_valid(self):
        """Check the tag is valid"""

        # type has to be a JSON-serialisable type, Number or a TaggedAggregateType.

        def check_type(t):
            # check a single type is json-serialisable, TaggedAggregate or Number
            if t in (int, float, str, bool, list, dict, tuple, np.ndarray):
                return
            if isinstance(t, TaggedAggregateType):
                return
            if t is Number or t is type(None):
                return
            raise ValueError(f"Type {t} is neither a JSON-serialisable type nor a TaggedAggregateType")

        if isinstance(self.type, Maybe):
            # check the type is valid
            check_type(self.type.type_if_exists)
        else:
            check_type(self.type)


class TaggedDictType(TaggedAggregateType):
    """This acts like a dictionary, but each item has a type, description and default value. That means
    that it must be initialised with a set of such values. This is done by calling the constructor like this:
    ```
    tdt = TaggedDictType(
        a=("description of a", int, 3),
        b=("description of b", str, "hello"),
        c=("a nested tagged dict", someOtherTaggedDictType, None)
        )
    ```
    Note that the default value is ignored if the type is a TaggedAggregateType, because these have their own
    defaults.

    For Maybe types the default can either be None or the underlying type - unless the type is a TaggedAggregateType,
    in which case None should be used.

    If a TaggedDict is ordered (by calling setOrdered) then:

    * it will be serialised/deserialised as a tuple
    * elements can be accessed by integer indices
    * get() will return a list of elements
    * set() can take a variable number of arguments to set elements (i.e. it is `def set(*args)`)
    * it can create iterators
    * the order is that given in the constructor

    You might think that all dicts should work this way - it provides more functionality and saves
    more efficientiy - but it should only be used sparingly. Serialising as a tuple causes problems
    with backcompatibility if the dict should change later - generally a dict will be more forgiving,
    but a savefile with a tuple in it is more likely to fail.

    It is currently only used for values where the fields are obvious and unlikely to change, such as
    colour (r,g,b), rectangles (x,y,w,h) and points (x,y).
    """

    tags: Dict[str, Tag]

    # in legacy data some TD's may be serialised as a tuple. This gives the ordering of elements.
    ordering: Optional[List[str]]
    # but it's only used if this is true
    isOrdered: bool

    def __init__(self, *args, **kwargs):
        """Initialise the dictionary with a set of key-value pairs, where the value is a tuple of
        (description, type, default). You can also specify these as kwargs.

        If the type is a TaggedAggregateType, then the default value is ignored and should be None or omitted (the
        create method for that type will create the correct default).
        Otherwise the default value should be of the correct type.
        """

        super().__init__()

        self.tags = {}
        self.ordering = []
        self.isOrdered = False

        for k, v in args:
            self.tags[k] = Tag(*v)
            self.ordering.append(k)

        for k, v in kwargs.items():
            self.tags[k] = Tag(*v)
            self.ordering.append(k)

        for k, v in self.tags.items():
            v.assert_valid()
            # if type is a TaggedAggregate the default has to be None
            if isinstance(v.type, TaggedAggregateType):
                if v.deflt is not None:
                    raise ValueError(f"Type {v.type} is a TaggedAggregateType, so default must be None")
            # otherwise the default has to be of the correct type
            elif not is_value_of_type(v.deflt, v.type):
                raise ValueError(f"Default {v.deflt} is not of type {v.type}")

    def tag(self, key):
        """Return the tag for a given key - raises a key error on failure"""
        return self.tags[key]

    def setOrdered(self) -> 'TaggedDictType':
        """Make the dict ordered, so it will be serialised and deserialised as a tuple/list and can use integer keys.
        The key ordering will be that given in the constructor."""
        self.isOrdered = True
        return self

    def create(self):
        """Create a the appropriate default values"""
        return TaggedDict(self)

    def deserialise(self, data) -> 'TaggedDict':
        """Create a new TaggedDict of this type from a JSON-serialisable structure. It's important that data can
        have a subset or superset of the keys of the TaggedDict."""
        return TaggedDict(self, data)


class TaggedDict(TaggedAggregate):
    """This is the actual tagged dict object. It acts like a dict, in that you can set and get
    values by key, but each value has a type, description and default value stored in the type object.
    You can also access items as attributes - so if you have a TaggedDict with a tag 'foo', you can
    use tag.foo"""

    _values: Dict[str, Any]
    _type: TaggedDictType

    def __init__(self, td: TaggedDictType, data: Optional[dict] = None):
        """Initialise the TaggedDict with a TaggedDictType. If a dict is provided, use the values therein instead
        of the defaults given in the type object"""
        super().__init__(td)
        self._values = {}

        if isinstance(data, list) or isinstance(data, tuple):
            # we have legacy data that has been serialised as tuple or list. Deal with it by converting to a dict -
            # we need to know what the ordering is.
            if not td.isOrdered:
                raise ValueError("TaggedDictType has no ordering, but data is a tuple")
            if len(td.ordering) > len(data):
                raise ValueError("Not enough keys in TaggedDictType for data")

            data = {k: v for k, v in zip(td.ordering, data)}

        # go through the items. This is a bit horrid because of how the maybe processing is done.
        for k, v in td.tags.items():
            if data is not None and k in data:
                d = data[k]
                # if we have data, use that instead of the defaults.
                if isinstance(v.type, TaggedAggregateType):
                    # if we have a tagged aggregate, create it from the data stored in the serialised dict
                    self._values[k] = v.type.deserialise(d)
                elif isinstance(v.type, Maybe):
                    # if we have a maybe, we have to check null.
                    if d is None:
                        self._values[k] = None
                    elif isinstance(v.type.type_if_exists, TaggedAggregateType):
                        # it's not a null, so use the underlying type to deserialise - first the TA case
                        self._values[k] = v.type.type_if_exists.deserialise(d)
                    elif not is_value_of_type(d, v.type.type_if_exists):
                        # then the "normal" case.
                        raise ValueError(f"TaggedDict key {k}: Value {d} is not of type {v.type.type_if_exists}")
                    else:
                        self._values[k] = d
                else:
                    # otherwise just use the data as is
                    if not is_value_of_type(d, v.type):
                        raise ValueError(f"TaggedDict key {k}: Value {d} is not of type {v.type}")
                    self._values[k] = d
            else:
                # we are creating from defaults
                if isinstance(v.type, TaggedAggregateType):
                    # just create a default object for this type
                    self._values[k] = v.type.create()
                else:
                    # use default as is (type should have been checked). Make sure we use a copy of the default
                    # (it could, in rare cases, be a mutable object like a dict).
                    self._values[k] = copy(v.deflt)

    def _intkey2str(self, key):
        """Convert an integer key to a string key"""
        if isinstance(key, int):
            if not self._type.isOrdered:
                raise KeyError("No ordering for TaggedDict, can't use integer keys")
            key = self._type.ordering[key]
        return key

    def __getitem__(self, key):
        """Return the value for a given key"""
        try:
            key = self._intkey2str(key)
            return self._values[key]
        except KeyError as e:
            raise KeyError(f"Key {key} not in TaggedDict: valid keys are {','.join(self.keys())}") from e

    def __setitem__(self, key, value):
        """Set the value for a given key. Will raise KeyError if it's not in the tags,
        and ValueError if the value is not of the correct type."""
        tp = self._type
        if key not in tp.tags:
            raise KeyError(f"Key {key} not in tags")
        key = self._intkey2str(key)
        correct_type = tp.tags[key].type
        if isinstance(correct_type, Maybe):
            if value is None:
                self._values[key] = None
                return
            else:
                correct_type = correct_type.type_if_exists
        if isinstance(correct_type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"TaggedDict key {key}: Value {value} is not a TaggedAggregate")
            if correct_type != value._type:
                raise ValueError(f"TaggedDict key {key}: Value {value} is not a TaggedAggregate of type {correct_type}")
        elif not is_value_of_type(value, correct_type):
            # otherwise check the type
            raise ValueError(f"TaggedDict key {key}: Value {value} is not of type {correct_type}")

        # this will convert the value to the exact type declared in the tag if possible
        if correct_type in (int, float, str, bool):
            self._values[key] = correct_type(value)
        else:
            self._values[key] = value

    def set(self, *args) -> 'TaggedDict':
        """If there is an ordering, set the values in the order given."""
        if not self._type.isOrdered:
            raise ValueError("No ordering for TaggedDict")
        if len(args) != len(self._type.ordering):
            raise ValueError("Wrong number of arguments")
        for k, v in zip(self._type.ordering, args):
            self[k] = v
        return self

    def get(self) -> List[Any]:
        """If there is an ordering, return the values as a list in the order given"""
        if not self._type.isOrdered:
            raise ValueError("No ordering for TaggedDict")
        return [self[k] for k in self._type.ordering]

    astuple = get
    aslist = get

    def isNotDefault(self, key) -> bool:
        """True if a value is not equal to the default stored for that key - i.e. it has been set in
        the parameter file"""
        key = self._intkey2str(key)
        return self._values[key] != self._type.tags[key].deflt

    def __iter__(self):
        return iter(self.get())

    def __getattr__(self, key):
        """Allow access to the values by name. This is only called when it's NOT found in the usual places"""
        return self._values[key]

    def __setattr__(self, key, value):
        """Allow setting the values by name"""
        if key in ('_values', '_type'):
            super().__setattr__(key, value)
        else:
            self[key] = value

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._values.keys()

    def __contains__(self, item):
        return item in self._values

    def items(self):
        return self._values.items()

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable structure. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        out = {}
        for k, v in self._values.items():
            tp = self._type.tags[k].type
            if isinstance(tp, Maybe):
                if v is None:
                    out[k] = None
                    continue
                tp = tp.type_if_exists
                # otherwise fall through with the underlying type, having assured the value isn't none.
            if isinstance(tp, TaggedAggregateType):
                out[k] = v.serialise()
            else:
                out[k] = v

        if self._type.isOrdered:
            # this is an ordered dict - we need to serialise as a tuple
            out = tuple([out[k] for k in self._type.ordering])

        return out


class TaggedListType(TaggedAggregateType):
    """This acts like a list, with all items having the same tag (type, description, default).
    Usually the description isn't used, since the containing tag will know what the list is for.
    """

    _tag: Tag       # tag giving description, default value of new lists, and type of values.
    deflt_append: Optional[Any]    # if a list of non-tagged-aggs, adding will append this.

    def tag(self, key=None) -> Tag:
        """All elements have the same type, so the key argument is ignored"""
        return self._tag

    def __init__(self, desc, tp, deflt=None, deflt_append=None):
        """Constructor for tagged list types.

        The deflt field specifies the initial value of the TaggedList that
        will be generated by create(). If the type is a TaggedAggregateType, then the deflt field gives
        the length of the list - otherwise it is a list of that type. For example:
        TaggedListType("description", int, [1,2,3]) will set the default to [1,2,3], while
        TaggedListType("description", TaggedDictType(foo=( "foo", int, 30)), 3) will set the default to 3 TaggedDict
        objects, each with a single integer value of 30.

        Often the description will be empty - this is because the parent type (usually a TaggedDictType) has
        a description for the item, rendering this description redundant.

        The deflt_append value is used when we append to a list of objects which are not tagged aggregates. For
        example, TaggedListType("desc", int, [1,2,3], 0) will create a list with 3 integers, and if we append to it
        we will append 0. If we append to a list of tagged aggregates, the default is to append a new object of the
        correct type, so a deflt_append value is not valid here (and we check for this).

        The deflt_append value must be provided for non-tagged-aggregate lists.
        """
        super().__init__()
        self._tag = Tag(desc, tp, deflt)
        self._tag.assert_valid()
        v = self._tag
        self.deflt_append = deflt_append   # not always valid to provide one; we check later.
        # if type is a TaggedAggregate the default has to be an int!
        if isinstance(v.type, TaggedAggregateType):
            if not isinstance(v.deflt, int):
                raise ValueError(
                    f"TaggedListType: Type {v.type.__class__.__name__} is a TaggedAggregateType, so default must be integer (number of items)")
            if deflt_append is not None:
                raise ValueError("A deflt_append value should not be provided for a list of tagged aggregates")
        else:
            # otherwise the default has to be a list, and all items must be of the correct type
            if not isinstance(v.deflt, list):
                raise ValueError(f"Default {v.deflt} is not a list")
            for i in v.deflt:
                if not is_value_of_type(i, v.type):
                    raise ValueError(f"Default {v.deflt} contains an item {i} that is not of type {v.type}")
            if self.deflt_append is None:
                raise ValueError("Default append not provided for non-TaggedAggregateType list")
            if not is_value_of_type(self.deflt_append, v.type):
                raise ValueError(f"Default append value {self.deflt_append} is not of type {v.type}")

    def create(self):
        """Create a the appropriate default values"""
        return TaggedList(self)

    def deserialise(self, data) -> 'TaggedList':
        """Create a new TaggedList of this type from a JSON-serialisable structure"""
        return TaggedList(self, data)


class TaggedList(TaggedAggregate):
    """This is the actual tagged list object"""

    _values: List[Any]
    _type: TaggedListType

    def __init__(self, tl: TaggedListType, data: Optional[List] = None):
        """Initialise the TaggedList with a TaggedListType"""
        super().__init__(tl)
        tt = tl.tag().type
        if data is not None:
            # data is provided.
            if isinstance(tt, TaggedAggregateType):
                # if the type is a tagged aggregate, them from the data provided
                self._values = [tt.deserialise(v) for v in data]
            else:
                # otherwise just use the data as is
                for v in data:
                    if not is_value_of_type(v, tt):
                        raise ValueError(f"Value {v} is not of type {tt}")
                self._values = data
        else:
            # we are creating from defaults
            if isinstance(tt, TaggedAggregateType):
                # if the type is a tagged aggregate, create the correct number of them
                self._values = [tt.create() for _ in range(tl.tag().deflt)]
            else:
                self._values = [v for v in tl.tag().deflt]  # create copies

    def __getitem__(self, idx):
        """Return the value for a given index"""
        try:
            return self._values[int(idx)]
        except ValueError as e:
            raise ValueError(f"List index {idx} is not an integer") from e

    def get(self) -> List[Any]:
        return self._values

    aslist = get

    def _check_value(self, value):
        """check an item before setting"""
        tp = self._type.tag().type
        if isinstance(tp, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"Value {value} is not a TaggedAggregate")
            if tp != value._type:
                raise ValueError(f"Value {value} is not a TaggedAggregate of type {tp}")
        elif not is_value_of_type(value, tp):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tp}")

    def __setitem__(self, idx, value):
        """Set the value for a given index. Will raise ValueError if the value is not of the correct type."""
        self._check_value(value)
        try:
            idx = int(idx)  # make sure it's an int; it will probably arrive as a string.
        except ValueError:
            raise TypeError(f"List index {idx} is not an integer")
        self._values[idx] = value

    def append(self, value):
        """Append a value to a list. If you want to append a default value, use append_default"""
        self._check_value(value)
        self._values.append(value)

    def append_default(self):
        """Append a default value to a list. If you want to append a specific value, use append"""
        if isinstance(self._type.tag().type, TaggedAggregateType):
            self._values.append(self._type.tag().type.create())
        elif self._type.deflt_append is not None:
            self._values.append(self._type.deflt_append)
        else:
            raise ValueError("Default append not provided for non-TaggedAggregateType list")

    def __len__(self):
        return len(self._values)

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable list. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        return [v.serialise() if isinstance(v, TaggedAggregate) else v for v in self._values]


class TaggedVariantDictType(TaggedAggregateType):
    """This is intended for by e.g. list containing ROIs, where ROIs are stored as TaggedDicts of different types,
    but each dict has a field which tells you what TaggedDictType it is. It's an oddly specific use case.."""

    discriminator_field: str  # the field that tells us what type we are
    type_dict: Dict[str, TaggedDictType]  # the types we can be

    def __init__(self, discriminator_field, type_dict):
        super().__init__()
        self.discriminator_field = discriminator_field
        self.type_dict = type_dict

        for k, v in type_dict.items():
            if not isinstance(v, TaggedDictType):
                raise ValueError(f"Value {v} is not a TaggedDictType")

    def create(self, type_name=None):
        """Create an instance of TaggedVariantDict. By default it will have no child dict, but if a name is provided
        it will
        - look up the name in the type_dict to get the type
        - create a new dict of that type and set it to be the child dict
        - set the value of the discriminator field in that dict to be the type name"""
        d = TaggedVariantDict(self)
        if type_name is not None:
            if type_name not in self.type_dict:
                poss = ",".join(self.type_dict.keys())
                raise KeyError(
                    f"{type_name} is not a valid variant for adding to this list. Possibilities are: {poss}")
            subd = self.type_dict[type_name].create()
            d.set(subd)
            subd[self.discriminator_field] = type_name
        return d

    def deserialise(self, data) -> 'TaggedVariantDict':
        return TaggedVariantDict(self, data)


class TaggedVariantDict(TaggedAggregate):
    """This is the actual tagged variant dict object"""

    _value: Optional[TaggedDict]
    _type: TaggedVariantDictType
    _type_name: Optional[str]

    def __init__(self, tt: TaggedVariantDictType, data: Optional[Dict] = None):
        super().__init__(tt)
        if data is None:
            # we initialise as containing no data
            self._value = None
            self._type_name = None
        else:
            # use the discriminator field to find the type
            if tt.discriminator_field not in data:
                raise ValueError(f"TaggedVariantDict does not have a discriminator field {tt.discriminator_field}")
            tp = data[tt.discriminator_field]
            if tp not in tt.type_dict:
                raise ValueError(f"TaggedVariantDict does not have a type {tp} in the type dictionary")
            # we should now be ready to deserialise the TaggedDict
            self._value = tt.type_dict[tp].deserialise(data)
            self._type_name = tp

    def get(self) -> TaggedDict:
        """return the underlying TaggedDict"""
        return self._value

    def set(self, td):
        """Set the value to a tagged dict, making sure it's of the correct type. Fluent - returns self."""
        if td._type not in self._type.type_dict.values():
            raise ValueError(f"TaggedVariantDict does not have a type {td._type} in the type dictionary")
        self._value = td
        for k, v in self._type.type_dict.items():
            if v == td._type:
                self._type_name = k
                return self
        raise ValueError("Internal error - type not found in type dictionary")

    def get_type(self):
        """return the name of the underlying TaggedDict"""
        return self._type_name

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable structure. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""
        if self._value is None:
            return None
        out = self._value.serialise()
        # make very sure that the discriminator is set
        out[self._type.discriminator_field] = self._type_name
        return out


#
# Special aggregates we use a lot
#

def taggedColourType(r, g, b):
    return TaggedDictType(r=("The red component 0-1", Number, float(r)),
                           g=("The green component 0-1", Number, float(g)),
                           b=("The blue component 0-1", Number, float(b))).setOrdered()


def taggedRectType(x, y, w, h):
    return TaggedDictType(x=("The x coordinate of the top left corner", int, int(x)),
                           y=("The y coordinate of the top left corner", int, int(y)),
                           w=("The width of the rectangle", int, int(w)),
                           h=("The height of the rectangle", int, int(h))
                           ).setOrdered()
