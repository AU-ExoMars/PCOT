import dataclasses
from typing import Any, Dict, Union, List, Tuple, Optional
from abc import ABC, abstractmethod


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
    tp: TaggedAggregateType  # will always be the appropriate subtype of TaggedAggregateType

    def __init__(self, tp: TaggedAggregateType):
        self.type = tp

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
        # type has to be a JSON-serialisable type or a string
        if not (self.type in (int, float, str, bool, list, dict, tuple) or isinstance(self.type, TaggedAggregateType)):
            raise ValueError(f"Type {self.type} is neither a JSON-serialisable type nor a TaggedAggregateType")


class TaggedDictType(TaggedAggregateType):
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
            elif not isinstance(v.deflt, v.type):
                raise ValueError(f"Default {v.deflt} is not of type {v.type}")

    def tag(self, key):
        """Return the tag for a given key"""
        return self.tags[key]

    def create(self):
        """Create a the appropriate default values"""
        return TaggedDict(self)

    def deserialise(self, data) -> 'TaggedDict':
        """Create a new TaggedDict of this type from a JSON-serialisable structure"""
        return TaggedDict(self, data)


class TaggedDict(TaggedAggregate):
    """This is the actual tagged dict object"""

    values: Dict[str, Any]
    type: TaggedDictType

    def __init__(self, td: TaggedDictType, data: Optional[dict] = None):
        """Initialise the TaggedDict with a TaggedDictType. If a dict is provided, use the values therein instead
        of the defaults given in the type object"""
        super().__init__(td)
        self.values = {}
        # easier to read than a dict comprehension
        for k, v in td.tags.items():
            if data is not None and k in data:
                # if we have data, use that instead of the defaults.
                if isinstance(v.type, TaggedAggregateType):
                    # if we have a tagged aggregate, create it from the data stored in the serialised dict
                    self.values[k] = v.type.deserialise(data[k])
                else:
                    # otherwise just use the data as is
                    self.values[k] = data[k]
            else:
                # we are creating from defaults
                if isinstance(v.type, TaggedAggregateType):
                    # just create a default object for this type
                    self.values[k] = v.type.create()
                else:
                    # use default as is
                    self.values[k] = v.deflt

    def __getitem__(self, key):
        """Return the value for a given key"""
        return self.values[key]

    def __setitem__(self, key, value):
        """Set the value for a given key. Will raise KeyError if it's not in the tags,
        and ValueError if the value is not of the correct type."""
        tp = self.type
        if key not in tp.tags:
            raise KeyError(f"Key {key} not in tags")
        tag = tp.tags[key]
        if isinstance(tag.type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"Value {value} is not a TaggedAggregate")
            if tag.type != value.tp:
                raise ValueError(f"Value {value} is not a TaggedAggregate of type {self.tags[key].type}")
        elif not isinstance(value, tag.type):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tag.type}")

        self.values[key] = value

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable structure. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        return {k: (v.serialise() if isinstance(v, TaggedAggregate) else v) for k, v in self.values.items()}


class TaggedTupleType(TaggedAggregateType):
    """This acts like a tuple, but each item has a type, description and default value. That means
    that it must be initialised with a set of such values.
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
            elif not isinstance(v.deflt, v.type):
                raise ValueError(f"Default {v.deflt} is not of type {v.type}")

    def create(self):
        """Create a the appropriate default values"""
        return TaggedTuple(self)

    def deserialise(self, data) -> 'TaggedTuple':
        """Create a new TaggedTuple of this type from a JSON-serialisable structure"""
        return TaggedTuple(self, data)


class TaggedTuple(TaggedAggregate):
    """This is the actual tagged tuple object"""

    # while we *serialise* as a tuple, we're stored as a list - otherwise
    # we wouldn't be able to change the values
    values: List[Any]
    type: TaggedTupleType

    def __init__(self, tt: TaggedTupleType, data: Optional[Tuple] = None):
        """Initialise the TaggedTuple with a TaggedTupleType.
        If a tuple is provided, use the values therein instead of the defaults
        given in the type object"""
        super().__init__(tt)
        if data is not None:
            self.values = []
            if len(data) != len(tt.tags):
                raise ValueError(f"Data {data} does not match tags {tt.tags}")
            # run through the tags and the data
            for i, v in enumerate(data):
                tagname, tag = tt.tags[i]
                if isinstance(tag.type, TaggedAggregateType):
                    # if the type is a tagged aggregate, create it from the data stored in the serialised tuple
                    self.values.append(tag.type.deserialise(v))
                else:
                    # otherwise just use the data as is
                    self.values.append(v)
        else:
            self.values = [v.deflt for k, v in tt.tags]

    def __getitem__(self, idxOrKey: Union[int, str]):
        """Return the value for a given index OR tagname"""
        if isinstance(idxOrKey, str):
            # if it's a string, look up the index
            idxOrKey = self.type.indicesByName[idxOrKey]
        return self.values[idxOrKey]

    def __setitem__(self, idxOrKey, value):
        """Set the value for a given key or index. Will raise KeyError if it's not in the tags,
        and ValueError if the value is not of the correct type."""
        tp = self.type
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
        elif not isinstance(value, tag.type):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tag.type}")

        self.values[idx] = value

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable tuple. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        # return a tuple
        return tuple([(v.serialise() if isinstance(v, TaggedAggregate) else v) for v in self.values])


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
                if not isinstance(i, v.type):
                    raise ValueError(f"Default {v.deflt} contains an item {i} that is not of type {v.type}")

    def create(self):
        """Create a the appropriate default values"""
        return TaggedList(self)

    def deserialise(self, data) -> 'TaggedList':
        """Create a new TaggedTuple of this type from a JSON-serialisable structure"""
        return TaggedList(self, data)


class TaggedList(TaggedAggregate):
    """This is the actual tagged list object"""

    values: List[Any]
    type: TaggedListType

    def __init__(self, tl: TaggedListType, data: Optional[List] = None):
        """Initialise the TaggedList with a TaggedListType"""
        super().__init__(tl)
        if data is not None:
            # data is provided.
            if isinstance(tl.tag.type, TaggedAggregateType):
                # if the type is a tagged aggregate, them from the data provided
                self.values = [tl.tag.type.deserialise(v) for v in data]
            else:
                # otherwise just use the data as is
                self.values = data
        else:
            # we are creating from defaults
            if isinstance(tl.tag.type, TaggedAggregateType):
                # if the type is a tagged aggregate, create the correct number of them
                self.values = [tl.tag.type.create() for _ in range(tl.tag.deflt)]
            else:
                self.values = [v for v in tl.tag.deflt]  # create copies

    def __getitem__(self, idx):
        """Return the value for a given index"""
        return self.values[idx]

    def __setitem__(self, idx, value):
        """Set the value for a given index. Will raise ValueError if the value is not of the correct type."""
        tp = self.type
        if isinstance(tp.tag.type, TaggedAggregateType):
            # if the type is a tagged aggregate, make sure it's the right type
            if not isinstance(value, TaggedAggregate):
                raise ValueError(f"Value {value} is not a TaggedAggregate")
            if tp.tag.type != value.tp:
                raise ValueError(f"Value {value} is not a TaggedAggregate of type {tp.tag.type}")
        elif not isinstance(value, tp.tag.type):
            # otherwise check the type
            raise ValueError(f"Value {value} is not of type {tp.tag.type}")

        self.values[idx] = value

    def serialise(self):
        """Serialise the structure rooted here into a JSON-serialisable list. We don't need to record what the
        types are, because that information will be stored in the type object when we deserialise.
        This assumes that the only items in the structure are JSON-serialisable or TaggedAggregate."""

        return [v.serialise() if isinstance(v, TaggedAggregate) else v for v in self.values]


#
# Special aggregates we use a lot
#

taggedColour = TaggedTupleType(r=("The red component 0-1", float, 0.0),
                               g=("The green component 0-1", float, 0.0),
                               b=("The blue component 0-1", float, 0.0))
