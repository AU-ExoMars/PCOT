import os
import pathlib

import pytest
from distutils import dir_util


@pytest.fixture
def datadir(tmp_path, request):
    """
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely. Returns a pathlib.

    To use this, the data files need to be in a directory with the same name as the test module,
    with "_data" added:
    e.g. "test_foo.py" needs a directory called "test_foo_data" in the same place.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    test_dir += "_data"
    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmp_path))
    else:
        raise Exception(f"Test data directory {test_dir} does not exist")

    return tmp_path


@pytest.fixture
def globaldatadir(tmp_path, request):
    """
    As datadir, but this uses the "PCOT/tests/data" directory rather than a per-module directory.
    """
    path = pathlib.Path(request.module.__file__).resolve()
    # walk the module's path until we find an element called "tests" which has a child called "data"
    parents = path.parents
    for i in range(len(parents)-1):
        if parents[i].name == 'tests' and (parents[i] / 'data').exists():
            xx = parents[i] / 'data'
            return xx
    raise FileNotFoundError(f"cannot find tests/data in parents of test directory {path}")
