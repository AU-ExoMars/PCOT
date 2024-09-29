import pytest

from pcot.parameters.parameterfile import ParameterFile


def test_path_absolute():
    f = ParameterFile()
    p, k = f._parse_path(0, "foo")
    assert p == []
    assert k == "foo"

    p, k = f._parse_path(0, "foo.bar")
    assert p == ["foo"]
    assert k == "bar"

    p, k = f._parse_path(0, "foo.bar.baz")
    assert p == ["foo", "bar"]
    assert k == "baz"


def test_path_relative():
    f = ParameterFile()
    f._parse_path(0, "foo.bar.baz")

    p, k = f._parse_path(0, ".quux")
    assert p == ["foo", "bar"]
    assert k == "quux"

    p, k = f._parse_path(0, ".quux.blah")
    assert p == ["foo", "bar", "quux"]
    assert k == "blah"

    p, k = f._parse_path(0, "foo.bar.quux.blah")
    assert p == ["foo", "bar", "quux"]
    assert k == "blah"
    p, k = f._parse_path(0, ".x")
    assert p == ["foo", "bar", "quux"]
    assert k == "x"
    p, k = f._parse_path(0, "..y")
    assert p == ["foo", "bar"]
    assert k == "y"


def test_path_indexed():
    f = ParameterFile()
    p, k = f._parse_path(0, "foo.bar[1]")
    assert p == ["foo", "bar"]
    assert k == "1"

    p, k = f._parse_path(0, "foo.bar[1][2]")
    assert p == ["foo", "bar", "1"]
    assert k == "2"

    p, k = f._parse_path(0, "foo[1].bar[2]")
    assert p == ["foo", "1", "bar"]
    assert k == "2"

    p, k = f._parse_path(0, "foo[1].bar[2].baz")
    assert p == ["foo", "1", "bar", "2"]
    assert k == "baz"

    p, k = f._parse_path(0, "foo.bar[1].quux")
    assert p == ["foo", "bar", "1"]
    assert k == "quux"


def test_adhoc():
    test ="""
    foo.bar[1].quux = "world"
    """
    f = ParameterFile().parse(test)
    print(f._changes[0])


def test_string():
    test ="""
    # this is a comment
    foo.bar.baz = 1
    foo.bar.quux = "hello"      # this is an end-of-line comment
    foo.bar[1] = 2
    foo.bar[1].quux = "world"
    .blonk = 3
    del foo.bar[1]
    """
    f = ParameterFile().parse(test)
    assert repr(f._changes[0]) == "SetValue(2, root=foo path=bar key=baz) val=1"
    assert repr(f._changes[1]) == 'SetValue(3, root=foo path=bar key=quux) val="hello"'
    assert repr(f._changes[2]) == 'SetValue(4, root=foo path=bar key=1) val=2'
    assert repr(f._changes[3]) == 'SetValue(5, root=foo path=bar.1 key=quux) val="world"'
    assert repr(f._changes[4]) == 'SetValue(6, root=foo path=bar.1 key=blonk) val=3'
    assert repr(f._changes[5]) == 'DeleteValue(7, root=foo path=bar key=1)'


def test_list_add_at_root_invalid():
    with pytest.raises(ValueError):
        f = ParameterFile().parse("root+")


def test_list_adds():
    test = """
    foo.bar.+        # add an item at node foo.bar, with default values. Set the path to foo.bar.-1
    .a = 1          # change foo.bar.a.-1 to 1
    .b = 2          # change foo.bar.b.-1 to 2
    foo.bar.+.a = 1  # add an item at foo.bar, with a=1. Set the path to foo.bar.-1.
    .b = 2          # change foo.bar.b.-1 to 2
    """
    f = ParameterFile().parse(test)
    assert repr(f._changes.pop(0)) == "Add(1, root=foo path= key=bar)"
    assert repr(f._changes.pop(0)) == "SetValue(2, root=foo path=bar.-1 key=a) val=1"
    assert repr(f._changes.pop(0)) == "SetValue(3, root=foo path=bar.-1 key=b) val=2"
    assert repr(f._changes.pop(0)) == "Add(4, root=foo path= key=bar)"
    assert repr(f._changes.pop(0)) == "SetValue(4, root=foo path=bar.-1 key=a) val=1"
    assert repr(f._changes.pop(0)) == "SetValue(5, root=foo path=bar.-1 key=b) val=2"


def test_list_adds_partial():
    test = """
    foo.bar.+        # add an item at node foo.bar, with default values. Set the path to foo.bar.-1
    .a = 1          # change foo.bar.-1.a to 1
    .b = 2          # change foo.bar.-1.b to 2

    ..+.a = 1       # add an item at foo.bar, with a=1. Set the path to foo.bar.-1.
    .b = 2          # change foo.bar.-1.b to 2
    """
    f = ParameterFile().parse(test)
    assert repr(f._changes.pop(0)) == "Add(1, root=foo path= key=bar)"
    assert repr(f._changes.pop(0)) == "SetValue(2, root=foo path=bar.-1 key=a) val=1"
    assert repr(f._changes.pop(0)) == "SetValue(3, root=foo path=bar.-1 key=b) val=2"
    assert repr(f._changes.pop(0)) == "Add(5, root=foo path= key=bar)"
    assert repr(f._changes.pop(0)) == "SetValue(5, root=foo path=bar.-1 key=a) val=1"
    assert repr(f._changes.pop(0)) == "SetValue(6, root=foo path=bar.-1 key=b) val=2"


def test_list_adds_variant():
    test = """
    foo.bar.+rect   # add an item at node foo.bar which will be a rectangle. Foo.bar must be list of variants, 
                    # and rect must be a valid variant within it. Set the path to foo.bar.-1
    .a = 1          # change foo.bar.-1(.rect).a to 1
    """
    f = ParameterFile().parse(test)
    assert repr(f._changes.pop(0)) == "Add(1, root=foo path= key=bar variant=rect)"
    # the generated change doesn't mention "rect" at all because of how
    # get_element_to_modify works - it will automatically do a get() in the variant layer.
    # We jump straight from the variant to the containing dict.
    assert repr(f._changes.pop(0)) == "SetValue(3, root=foo path=bar.-1 key=a) val=1"
