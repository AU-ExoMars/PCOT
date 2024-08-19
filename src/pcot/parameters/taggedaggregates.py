import dataclasses
from abc import ABC, abstractmethod
from numbers import Number
from typing import Any, Dict, Union, List, Tuple, Optional

import numpy as np


class Maybe:
    """Objects of this class wrap both type objects ('int' etc) and TaggedAggregateType objects, to indicate that
    this is optional in a type hint. We can't use Optional because it woon't work with TaggedAggregateType objects

    We did have an Amalgam object, but that can't possibly work because we don't actually store type data in
    the serialisation so we can't tell what to deserialise to. Maybe only works because we can check for None.
    """

    def __init__(self, tp):
        self.tp = tp

    def __repr__(self):
        return f"Maybe({self.tp})"


def is_value_of_type(value, tp):
    """Type checker that is aware of "Maybe"
    This doesn't do what check_type inside the constructors do - that checks that the type is OK, this checks
    that a value matches a type."""
    if isinstance(tp, Maybe):
        # check the value is None or of the correct type
        return value is None or is_value_of_type(value, tp.tp)
    if tp is type(None):  # NoneType isn't available anywhere, but there's only one None and one NoneType
        return value is None
    if isinstance(tp, TaggedAggregateType):
        # are we expecting a tagged aggregate?
        if isinstance(value, TaggedAggregate):
            # it's a tagged agg, but not the right type.
            return tp == value._type
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
            check_type(self.type.tp)
        else:
            check_type(self.type)


class DictLikeType(TaggedAggregateType, ABC):
    """
    Acts like a dictionary or a named tuple.
    """

    def tag(self, key) -> Tag:
        """Return the tag for a given key"""
        pass


class TaggedDictType(DictLikeType):
    """This acts like a dictionary, but each item has a type, description and default value. That means
    that it must be initialised with a set of such values.
    """

    tags: Dict[str, Tag]

    def __init__(self, *args, **kwargs):
        """Initialise the dictionary with a set of key-value pairs, where the value is a tuple of
        (description, type, default). You can also specify these as kwargs.

        If the type is a TaggedAggregateType, then the default value is ignored and should be None or omitted (the
        create method for that type will create the correct default).
        Otherwise the default value should be of the correct type.
        """

        super().__init__()

        self.tags = {}
        for k, v in args:
            self.tags[k] = Tag(*v)

        for k, v in kwargs.items():
            self.tags[k] = Tag(*v)

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
                    elif isinstance(v.type.tp, TaggedAggregateType):
                        # it's not a null, so use the underlying type to deserialise - first the TA case
                        self._values[k] = v.type.tp.deserialise(d)
                    elif not is_value_of_type(d, v.type.tp):
                        # then the "normal" case.
                        raise ValueError(f"TaggedDict key {k}: Value {d} is not of type {v.type.tp}")
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
                    # use default as is (type should have been checked)
                    self._values[k] = v.deflt

    def __getitem__(self, key):
        """Return the value for a given key"""
        return self._values[key]

    def __setitem__(self, key, value):
        """Set the value for a given key. Will raise KeyError if it's not in the tags,
        and ValueError if the value is not of the correct type."""
        tp = self._type
        if key not in tp.tags:
            raise KeyError(f"Key {key} not in tags")
        correct_type = tp.tags[key].type
        if isinstance(correct_type, Maybe):
            if value is None:
                self._values[key] = None
                return
            else:
                correct_type = correct_type.tp
        if isinstance(correct_type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"TaggedDict key {key}: Value {value} is not a TaggedAggregate")
            if correct_type != value._type:
                raise ValueError(f"TaggedDict key {key}: Value {value} is not a TaggedAggregate of type {correct_type}")
        elif not is_value_of_type(value, correct_type):
            # otherwise check the type
            raise ValueError(f"TaggedDict key {key}: Value {value} is not of type {correct_type}")

        self._values[key] = value

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
                # otherwise fall through with the underlying type, having assured the value isn't none.
                tp = tp.tp
            if isinstance(tp, TaggedAggregateType):
                out[k] = v.serialise()
            else:
                out[k] = v
        return out


class TaggedTupleType(DictLikeType):
    """This acts like a tuple, but each item has a type, description and default value. That means
    that it must be initialised with a set of such values.
    It works like a TaggedDict in many ways, so if there is a "foo" entry you could access it with
    tag.foo as well as tag[0] and tag["foo"] (assuming foo's index is 0 of course).
    """

    tags: List[Tuple[str, Tag]]  # the name and tag for each item
    indicesByName: Dict[str, int]  # a dictionary of indices by name

    def __init__(self, *args, **kwargs):
        """Initialise the tuple with a set of key-value pairs, where the value is a tuple of
        (description, type, default). You can also specify these as kwargs.
        If the type is a TaggedAggregateType, then the default value is ignored and should be None or omitted (the
        create method for that type will create the correct default).
        Otherwise the default value should be of the correct type.
        """

        super().__init__()

        def addTag(kk, vv):
            t = Tag(*vv)
            self.indicesByName[kk] = len(self.tags)
            self.tags.append((kk, t))

        self.tags = []
        self.indicesByName = {}
        for k, v in args:
            addTag(k, v)
        for k, v in kwargs.items():
            addTag(k, v)
        for k, v in self.tags:
            v.assert_valid()
            # if type is a TaggedAggregate the default has to be None
            if isinstance(v.type, TaggedAggregateType):
                if v.deflt is not None:
                    raise ValueError(f"Type {v.type} is a TaggedAggregateType, so default must be None")
            # otherwise the default has to be of the correct type
            elif not is_value_of_type(v.deflt, v.type):
                raise ValueError(f"Default {v.deflt} is not of type {v.type}")

    def create(self):
        """Create a the appropriate default values"""
        return TaggedTuple(self)

    def deserialise(self, data) -> 'TaggedTuple':
        """Create a new TaggedTuple of this type from a JSON-serialisable structure"""
        return TaggedTuple(self, data)

    def tag(self, key) -> Tag:
        """Return the tag for a given key - raises a key error on failure"""
        return self.tags[self.indicesByName[key]][1]


class TaggedTuple(TaggedAggregate):
    """This is the actual tagged tuple object"""

    # while we *serialise* as a tuple, we're stored as a list - otherwise
    # we wouldn't be able to change the values
    _values: List[Any]
    _type: TaggedTupleType

    def __init__(self, tt: TaggedTupleType, data: Optional[Tuple] = None):
        """Initialise the TaggedTuple with a TaggedTupleType.
        If a tuple is provided, use the values therein instead of the defaults
        given in the type object"""
        super().__init__(tt)
        if data is not None:
            self._values = []
            if len(tt.tags) > len(data):
                raise ValueError(f"Data {data} doesn't have enough to fill specification {tt.tags}")
            # run through the tags and the data
            for i, v in enumerate(data):
                # it can happen that there is more data than tags (usually due to redundant legacy
                # stuff). Just ignore it.
                if i < len(tt.tags):
                    tagname, tag = tt.tags[i]
                    if isinstance(tag.type, TaggedAggregateType):
                        # if the type is a tagged aggregate, create it from the data stored in the serialised tuple
                        self._values.append(tag.type.deserialise(v))
                    else:
                        # otherwise just use the data as is
                        if not is_value_of_type(v, tag.type):
                            raise ValueError(f"TaggedTuple index {i}: Value {v} is not of type {tag.type}")
                        self._values.append(v)
        else:
            self._values = [v.deflt for k, v in tt.tags]

    def __getitem__(self, idxOrKey: Union[int, str]):
        """Return the value for a given index OR tagname"""
        if isinstance(idxOrKey, str):
            # if it's a string, look up the index
            idxOrKey = self._type.indicesByName[idxOrKey]
        return self._values[idxOrKey]

    def __setitem__(self, idxOrKey, value):
        """Set the value for a given key or index. Will raise KeyError if it's not in the tags,
        and ValueError if the value is not of the correct type."""
        tp = self._type
        if isinstance(idxOrKey, str):
            # if it's a string, look up the index
            idx = tp.indicesByName[idxOrKey]
        else:
            idx = idxOrKey
        if idx >= len(tp.tags):
            raise KeyError(f"Key {idxOrKey} out of range")
        name, tag = tp.tags[idx]
        if isinstance(tag.type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"Value {value} is not a TaggedAggregate")
            if tag.type != value.tp:
                raise ValueError(f"Value {value} is not a TaggedAggregate of type {tag.type}")
        elif not is_value_of_type(value, tag.type):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tag.type}")

        self._values[idx] = value

    def __getattr__(self, item):
        """Allow access to the values by name"""
        idx = self._type.indicesByName[item]
        return self._values[idx]

    def __setattr__(self, key, value):
        """Allow setting the values by name"""
        if key in ('_values', '_type'):
            super().__setattr__(key, value)
        else:
            self[key] = value

    def set(self, *args):
        """Set the values from a list or tuple"""
        if len(args) != len(self._values):
            raise ValueError(f"Length of values {args} does not match tags {self._type.tags}")
        for i, v in enumerate(args):
            self[i] = v
        return self

    def get(self):
        """Return the data as an actual tuple"""
        return self._values

    astuple = get  # alias!

    def __len__(self):
        return len(self._values)

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable tuple. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        # return a tuple
        return tuple([(v.serialise() if isinstance(v, TaggedAggregate) else v) for v in self._values])


class TaggedListType(TaggedAggregateType):
    """This acts like a list, with all items having the same tag (type, description, default).
    """

    tag: Tag

    def __init__(self, desc, tp, deflt=None):
        """Initialise the list with a type. If the type is a TaggedAggregateType, then the deflt field gives
        the length of the list - otherwise it is a list of that type. For example:
        TaggedListType("description", int, [1,2,3]) will set the default to [1,2,3], while
        TaggedListType("description", TaggedTupleType(foo=( "foo", int, 30)), 3) will set the default to 3 TaggedTuple
        objects, each with a single integer value of 30.

        """
        super().__init__()
        self.tag = Tag(desc, tp, deflt)
        self.tag.assert_valid()
        v = self.tag
        # if type is a TaggedAggregate the default has to be an int!
        if isinstance(v.type, TaggedAggregateType):
            if not isinstance(v.deflt, int):
                raise ValueError(
                    f"TaggedListType: Type {v.type} is a TaggedAggregateType, so default must be integer (number of items)")
        else:
            # otherwise the default has to be a list, and all items must be of the correct type
            if not isinstance(v.deflt, list):
                raise ValueError(f"Default {v.deflt} is not a list")
            for i in v.deflt:
                if not is_value_of_type(i, v.type):
                    raise ValueError(f"Default {v.deflt} contains an item {i} that is not of type {v.type}")

    def create(self):
        """Create a the appropriate default values"""
        return TaggedList(self)

    def deserialise(self, data) -> 'TaggedList':
        """Create a new TaggedTuple of this type from a JSON-serialisable structure"""
        return TaggedList(self, data)


class TaggedList(TaggedAggregate):
    """This is the actual tagged list object"""

    _values: List[Any]
    _type: TaggedListType

    def __init__(self, tl: TaggedListType, data: Optional[List] = None):
        """Initialise the TaggedList with a TaggedListType"""
        super().__init__(tl)
        if data is not None:
            # data is provided.
            if isinstance(tl.tag.type, TaggedAggregateType):
                # if the type is a tagged aggregate, them from the data provided
                self._values = [tl.tag.type.deserialise(v) for v in data]
            else:
                # otherwise just use the data as is
                for v in data:
                    if not is_value_of_type(v, tl.tag.type):
                        raise ValueError(f"Value {v} is not of type {tl.tag.type}")
                self._values = data
        else:
            # we are creating from defaults
            if isinstance(tl.tag.type, TaggedAggregateType):
                # if the type is a tagged aggregate, create the correct number of them
                self._values = [tl.tag.type.create() for _ in range(tl.tag.deflt)]
            else:
                self._values = [v for v in tl.tag.deflt]  # create copies

    def __getitem__(self, idx):
        """Return the value for a given index"""
        return self._values[idx]

    def get(self):
        return self._values

    aslist = get

    def _check_value(self, value):
        """check an item before setting"""
        tp = self._type
        if isinstance(tp.tag.type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"Value {value} is not a TaggedAggregate")
            if tp.tag.type != value._type:
                raise ValueError(f"Value {value} is not a TaggedAggregate of type {tp.tag.type}")
        elif not is_value_of_type(value, tp.tag.type):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tp.tag.type}")

    def __setitem__(self, idx, value):
        """Set the value for a given index. Will raise ValueError if the value is not of the correct type."""
        self._check_value(value)
        self._values[idx] = value

    def append(self, value):
        """Append a value to a list. If you want to append a default value, use append_default"""
        self._check_value(value)
        self._values.append(value)

    def append_default(self):
        """Append a default value to a list. If you want to append a specific value, use append"""
        if isinstance(self._type.tag.type, TaggedAggregateType):
            self._values.append(self._type.tag.type.create())
        else:
            raise ValueError("Can't append default to non-TaggedAggregateType list")

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

    def create(self):
        return TaggedVariantDict(self)

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

    def get(self):
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
    return TaggedTupleType(r=("The red component 0-1", Number, float(r)),
                           g=("The green component 0-1", Number, float(g)),
                           b=("The blue component 0-1", Number, float(b)))


def taggedRectType(x, y, w, h):
    return TaggedTupleType(x=("The x coordinate of the top left corner", Number, float(x)),
                           y=("The y coordinate of the top left corner", Number, float(y)),
                           w=("The width of the rectangle", Number, float(w)),
                           h=("The height of the rectangle", Number, float(h))
                           )
