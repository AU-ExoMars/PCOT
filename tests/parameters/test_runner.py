import os
import tempfile

import pytest

import pcot
from pcot.datum import Datum
from pcot.parameters.runner import Runner
from fixtures import globaldatadir


def test_create_runner(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")


def test_noparams(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")
    r.run(None)


def test_with_input(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")

    test = f"""
    inputs.0.rgb.filename = {globaldatadir / 'basn2c16.png'}  # colour image
    """
    r.run(None, test)


def test_run(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")

    out = tempfile.NamedTemporaryFile(suffix=".png")

    test = f"""
    inputs.0.rgb.filename = {globaldatadir / 'basn2c16.png'}  # colour image
    outputs.+.file = {out.name}
    .node = sink
    """
    r.run(None, test)


def test_run_scalar_output(globaldatadir):
    """This tests a graph which should produce a scalar output (among other things), but it will
    also test we can read an image from a multi-image PARC file and modify a constant node"""

    pcot.setup()
    r = Runner(globaldatadir / "test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out}
        .node = mean
        """
        r.run(None, test)

        txt = open(out).read()
        assert txt == "0.45332±0.19508\n"

    # and again, modifying the constant
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out}
        .node = mean

        k.val = 2.4     # double the constant node
        """
        r.run(None, test)

        txt = open(out).read()
        assert txt == "0.90664±0.39016\n"   # double the previous value


def test_noclobber(globaldatadir):
    """Test that overwriting (clobbering) is not permitted by default, but we can change that"""

    pcot.setup()
    r = Runner(globaldatadir / "test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        # the block below shows a possible "prettyfication" of the test string
        test = f"""
        inputs.0.parc   .filename = {globaldatadir / 'parc/multi.parc'}
                        .itemname = image0
        outputs.+       .file = {out}
                        .node = mean
        """
        r.run(None, test)           # should run fine

        with pytest.raises(FileExistsError):
            r.run(None, test)       # should fail

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out}
        .clobber = y                # we set the clobber to yes
        .node = mean
        """

        r.run(None, test)           # should run fine
