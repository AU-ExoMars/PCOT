from pcot.parameters.parameterfile import ParameterFile


def test_path_absolute():
    f = ParameterFile()
    p, k = f._process_path("foo")
    assert p == []
    assert k == "foo"

    p, k = f._process_path("foo.bar")
    assert p == ["foo"]
    assert k == "bar"

    p, k = f._process_path("foo.bar.baz")
    assert p == ["foo", "bar"]
    assert k == "baz"


def test_path_relative():
    f = ParameterFile()
    f._process_path("foo.bar.baz")

    p, k = f._process_path(".quux")
    assert p == ["foo", "bar"]
    assert k == "quux"

    p, k = f._process_path(".quux.blah")
    assert p == ["foo", "bar", "quux"]
    assert k == "blah"

    p, k = f._process_path("foo.bar.quux.blah")
    assert p == ["foo", "bar", "quux"]
    assert k == "blah"
    p, k = f._process_path(".x")
    assert p == ["foo", "bar", "quux"]
    assert k == "x"
    p, k = f._process_path("..y")
    assert p == ["foo", "bar"]
    assert k == "y"


def test_path_indexed():
    f = ParameterFile()
    p, k = f._process_path("foo.bar[1]")
    assert p == ["foo", "bar"]
    assert k == "1"

    p, k = f._process_path("foo.bar[1][2]")
    assert p == ["foo", "bar", "1"]
    assert k == "2"

    p, k = f._process_path("foo[1].bar[2]")
    assert p == ["foo", "1", "bar"]
    assert k == "2"

    p, k = f._process_path("foo[1].bar[2].baz")
    assert p == ["foo", "1", "bar", "2"]
    assert k == "baz"

    p, k = f._process_path("foo.bar[1].quux")
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
    foo.bar.quux = "hello"
    foo.bar[1] = 2
    foo.bar[1].quux = "world"
    .blonk = 3
    del foo.bar[1]
    """
    f = ParameterFile().parse(test)
    assert repr(f._changes[0]) == "SetValue(2, foo.bar, baz, 1)"
    assert repr(f._changes[1]) == 'SetValue(3, foo.bar, quux, "hello")'
    assert repr(f._changes[2]) == 'SetValue(4, foo.bar, 1, 2)'
    assert repr(f._changes[3]) == 'SetValue(5, foo.bar.1, quux, "world")'
    assert repr(f._changes[4]) == 'SetValue(6, foo.bar.1, blonk, 3)'
    assert repr(f._changes[5]) == 'DeleteValue(7, foo.bar, 1)'

