"""
Tests for loading spectral parameter groups from YAML files: the builtin file and the user files listed
in the config (locations.userspecparams). Problems with user files must never stop PCOT starting - missing
files are skipped with a warning and bad files are ignored with an error, both recorded in
spectralparameters.errors for the UI to show later.
"""
from pathlib import Path

import pytest
import yaml

from pcot.assets import getAssetPath
from pcot.utils import spectralparameters as sp

BUILTIN = "data/builtin_spectral_parameters.yaml"

# a valid parameter, used to build test files
PARAM = {"expr": "a$671/a$438", "desc": "a ratio"}


def group(**kwargs):
    """Make a valid group body, with keys overridden by kwargs. A value of None removes the key."""
    g = {"desc": "a test group", "date": "2026-11-12", "parameters": {"p1": dict(PARAM)}}
    g.update(kwargs)
    return {k: v for k, v in g.items() if v is not None}


@pytest.fixture
def loader(tmp_path):
    """Provides an object which writes spectral parameter files into a temporary directory and runs the
    loader with those files as the user files. The loaded groups, the error list, the evaluator and the
    user file list in the (in-memory) config are all restored afterwards."""
    from pcot.config import data

    class Loader:
        def write(self, name, content) -> Path:
            """Write a file. Content is either a string (written as is) or a structure (dumped as YAML)."""
            p = tmp_path / name
            p.write_text(content if isinstance(content, str) else yaml.safe_dump(content))
            return p

        def missing(self, name="missing.yaml") -> Path:
            """Return a path in the temporary directory that doesn't exist"""
            return tmp_path / name

        def load(self, *paths):
            """Run the loader with these user files, returning the list of errors"""
            data.locations.userspecparams.set(list(paths))
            sp.loadSpectralParameters()
            return list(sp.errors)

    userlist = data.locations.userspecparams
    saved_paths = list(userlist.get())
    saved_groups = dict(sp.groups)
    saved_errors = list(sp.errors)
    saved_evaluator = sp._spectralEvaluator
    try:
        yield Loader()
    finally:
        userlist.set(saved_paths)
        # the groups dict is modified in place, because other modules may hold a reference to it.
        sp.groups.clear()
        sp.groups.update(saved_groups)
        sp.errors.clear()
        for tp, text in saved_errors:
            (sp.errors._add_warning if tp == "warn" else sp.errors._add_error)(text)
        sp._spectralEvaluator = saved_evaluator


@pytest.fixture
def builtin_names():
    """The names of the groups in the builtin file"""
    with open(getAssetPath(BUILTIN)) as f:
        return set(yaml.safe_load(f).keys())


def test_builtins_only(loader, builtin_names):
    """With no user files we get exactly the builtin groups and no errors"""
    assert loader.load() == []
    assert len(builtin_names) > 0
    assert set(sp.groups.keys()) == builtin_names
    for g in sp.groups.values():
        assert Path(g.path) == Path(getAssetPath(BUILTIN))


def test_user_file(loader, builtin_names):
    """A valid user file adds its groups to the builtins, and each group records the file it came from"""
    fn = loader.write("user.yaml", {
        "usergroup": group(desc="my group", parameters={
            "p1": {"expr": "a$671/a$438", "desc": "first"},
            "p2": {"expr": "a$671-a$438", "desc": "second"}}),
        "usergroup2": group()})
    assert loader.load(fn) == []
    assert set(sp.groups.keys()) == builtin_names | {"usergroup", "usergroup2"}

    g = sp.groups["usergroup"]
    assert g.desc == "my group"
    assert g.path == fn
    assert list(g.keys()) == ["p1", "p2"]
    assert g["p2"].name == "p2"
    assert g["p2"].expr == "a$671-a$438"
    assert g["p2"].desc == "second"
    assert g["p2"].compiled is not None


def test_multiple_user_files(loader, builtin_names):
    """Several user files can be loaded"""
    f1 = loader.write("one.yaml", {"g1": group()})
    f2 = loader.write("two.yaml", {"g2": group()})
    assert loader.load(f1, f2) == []
    assert set(sp.groups.keys()) == builtin_names | {"g1", "g2"}
    assert sp.groups["g1"].path == f1
    assert sp.groups["g2"].path == f2


def test_missing_file_is_warning(loader, builtin_names):
    """A file that doesn't exist is skipped with a warning (not an error)"""
    fn = loader.missing()
    errs = loader.load(fn)
    assert len(errs) == 1
    tp, text = errs[0]
    assert tp == "warn"
    assert str(fn) in text
    assert set(sp.groups.keys()) == builtin_names


def test_directory_is_warning(loader, tmp_path, builtin_names):
    """A directory in the list (e.g. an unedited default entry) is skipped with a warning"""
    errs = loader.load(tmp_path)
    assert [tp for tp, _ in errs] == ["warn"]
    assert set(sp.groups.keys()) == builtin_names


# files which should be rejected: (test name, file content, text expected in the error)
BAD_FILES = [
    ("badyaml", "foo: [unclosed\n", None),
    ("empty", "", "must be a dictionary of groups"),
    ("toplist", ["a", "b"], "must be a dictionary of groups"),
    ("groupnotdict", {"g": "just a string"}, "Group g"),
    ("nodesc", {"g": group(desc=None)}, "desc"),
    ("nodate", {"g": group(date=None)}, "date"),
    ("noparams", {"g": group(parameters=None)}, "parameters"),
    ("paramslist", {"g": group(parameters=["p1", "p2"])}, "must be a dictionary"),
    ("paramnotdict", {"g": group(parameters={"p1": "a$671"})}, "p1"),
    ("paramnoexpr", {"g": group(parameters={"p1": {"desc": "x"}})}, "expr"),
    ("paramnodesc", {"g": group(parameters={"p1": {"expr": "a$671"}})}, "desc"),
    ("badexpr", {"g": group(parameters={"p1": {"expr": "a$671 +", "desc": "x"}})}, "p1"),
]


@pytest.mark.parametrize("name,content,expected", BAD_FILES, ids=[x[0] for x in BAD_FILES])
def test_bad_file_is_error(loader, builtin_names, name, content, expected):
    """A malformed user file doesn't raise: it is reported as an error naming the file, and adds no groups"""
    fn = loader.write(name + ".yaml", content)
    errs = loader.load(fn)
    assert len(errs) == 1
    tp, text = errs[0]
    assert tp == "error"
    assert str(fn) in text
    if expected is not None:
        assert expected in text
    assert set(sp.groups.keys()) == builtin_names


@pytest.mark.parametrize("name,content,expected", BAD_FILES, ids=[x[0] for x in BAD_FILES])
def test_load_groups_raises(loader, builtin_names, name, content, expected):
    """The underlying _load_groups (used directly for the builtin file, where errors are fatal) raises
    on a malformed file and stores nothing"""
    loader.load()
    fn = loader.write(name + ".yaml", content)
    with pytest.raises(Exception):
        sp._load_groups(fn)
    assert set(sp.groups.keys()) == builtin_names


def test_redefine_builtin(loader, builtin_names):
    """A user file can't redefine a builtin group: the file is rejected and the builtin is untouched"""
    name = sorted(builtin_names)[0]
    fn = loader.write("redef.yaml", {name: group(desc="impostor")})
    errs = loader.load(fn)
    assert len(errs) == 1
    tp, text = errs[0]
    assert tp == "error"
    assert name in text
    assert "already exists" in text
    assert str(fn) in text
    assert set(sp.groups.keys()) == builtin_names
    assert sp.groups[name].desc != "impostor"
    assert Path(sp.groups[name].path) == Path(getAssetPath(BUILTIN))


def test_redefine_user_group(loader, builtin_names):
    """If two user files define the same group, the first wins and the second is rejected with an
    error naming both files"""
    f1 = loader.write("one.yaml", {"dup": group(desc="first")})
    f2 = loader.write("two.yaml", {"dup": group(desc="second")})
    errs = loader.load(f1, f2)
    assert len(errs) == 1
    tp, text = errs[0]
    assert tp == "error"
    assert str(f1) in text and str(f2) in text
    assert sp.groups["dup"].desc == "first"
    assert sp.groups["dup"].path == f1


def test_bad_file_is_all_or_nothing(loader, builtin_names):
    """If any group in a file is bad, none of the groups in that file are loaded - even those before
    the bad one"""
    fn = loader.write("partial.yaml", {"good": group(), "bad": group(date=None)})
    errs = loader.load(fn)
    assert [tp for tp, _ in errs] == ["error"]
    assert set(sp.groups.keys()) == builtin_names


def test_redefinition_is_all_or_nothing(loader, builtin_names):
    """A file with a new group and a redefinition of a builtin loads neither"""
    name = sorted(builtin_names)[0]
    fn = loader.write("partial.yaml", {"newgroup": group(), name: group()})
    errs = loader.load(fn)
    assert [tp for tp, _ in errs] == ["error"]
    assert set(sp.groups.keys()) == builtin_names


def test_good_files_survive_bad_ones(loader, builtin_names):
    """Problem files don't stop the other files loading, and problems are recorded in file order"""
    missing = loader.missing()
    bad = loader.write("bad.yaml", "foo: [unclosed\n")
    good1 = loader.write("good1.yaml", {"g1": group()})
    good2 = loader.write("good2.yaml", {"g2": group()})
    errs = loader.load(good1, missing, bad, good2)
    assert [tp for tp, _ in errs] == ["warn", "error"]
    assert str(missing) in errs[0][1]
    assert str(bad) in errs[1][1]
    assert set(sp.groups.keys()) == builtin_names | {"g1", "g2"}


def test_reload(loader, builtin_names):
    """The loader can be run more than once (pcot.setup() may be called several times): each run starts
    from scratch, so the builtins don't clash with themselves and old groups and errors don't persist"""
    good = loader.write("good.yaml", {"g1": group()})
    assert len(loader.load(good, loader.missing())) == 1
    assert "g1" in sp.groups
    # same again - no "already exists" errors, and the warning isn't duplicated
    assert len(loader.load(good, loader.missing())) == 1
    assert set(sp.groups.keys()) == builtin_names | {"g1"}
    # and with no user files, the user group and the warning go away
    assert loader.load() == []
    assert set(sp.groups.keys()) == builtin_names


def test_errors_clear(loader):
    """The error list can be cleared once it has been shown"""
    assert len(loader.load(loader.missing())) == 1
    sp.errors.clear()
    assert list(sp.errors) == []
