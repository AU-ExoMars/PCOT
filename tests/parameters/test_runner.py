import inspect
import os
import tempfile
import pytest
import pcot
from pcot.parameters.runner import Runner

from fixtures import *

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


def test_scalar_output(globaldatadir):
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


def test_vector_output(globaldatadir):
    """Test a graph that should produce vector out"""
    pcot.setup()
    r = Runner(globaldatadir / "test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out}
        .node = meanchans
        """
        r.run(None, test)

        txt = open(out).read()
        assert txt == "[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]\n"


def test_multiple_text_output_append(globaldatadir):
    """Test that we can use the append option to add to a file when we're doing text output"""

    pcot.setup()
    r = Runner(globaldatadir / "test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        
        outputs.+.file = {out}
        .node = meanchans
        
        outputs.+.file = {out}
        .node = mean
        .append = y
        """
        r.run(None, test)

        txt = open(out).read()
        assert txt == "[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]\n0.45332±0.19508\n"


def test_multiple_text_output_append_shorthand(globaldatadir):
    """Test that we can use the append option to add to a file when we're doing text output, using the "shorthand"
    that lets us use the previous filename and append mode by simply not specifying them.
    We also test output prefixes here."""

    pcot.setup()
    r = Runner(globaldatadir / "test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0

        outputs.+.file = {out}      # first file, specify the filename. Append will be false.
        .node = meanchans
        .prefix = "meanchans="      #asdasd

        ..+.node = mean             # second file, just specify the node. Set append to true.
        .append = y

        ..+.node = meanchansimage   # third file, just specify the node. Append will be same as last time
        ..+.node = meanimage        # fourth file, just specify the node. Append will be same as last time
        """
        r.run(None, test)

        txt = open(out).read()
        # inspect.cleandoc will remove the leading whitespace from the string, so we can format it nicely here,
        # but it will also remove the trailing newline, so we add it back in.
        assert txt == inspect.cleandoc("""[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]
            0.45332±0.19508
            [0.57216±0.16391, 0.3716±0.11629, 0.22292±0.080861]
            0.38889±0.19005
            """)+"\n"
