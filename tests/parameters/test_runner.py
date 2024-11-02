import datetime
import inspect
import os
import tempfile
import pytest
import pcot
from pcot.parameters.runner import Runner

from fixtures import *

def test_create_runner(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/doubler.pcot")


def test_noparams(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/doubler.pcot")
    r.run(None)


def test_with_input(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/doubler.pcot")

    test = f"""
    inputs.0.rgb.filename = {globaldatadir / 'basn2c16.png'}  # colour image
    """
    r.run(None, test)


def test_run(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/doubler.pcot")

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
    r = Runner(globaldatadir / "runner/test2.pcot")

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
    r = Runner(globaldatadir / "runner/test2.pcot")

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
    r = Runner(globaldatadir / "runner/test2.pcot")

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
    r = Runner(globaldatadir / "runner/test2.pcot")

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
    We also test output prefixes here and the idea that things in quotes will be unescaped using JSON"""

    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0

        outputs.+.file = {out}      # first file, specify the filename. Append will be false.
        .node = meanchans
        .prefix = "meanchans="      # will get prepended, but JSON-processed first.

        ..+.node = mean             # second file, just specify the node. Set append to true.
        .append = y
        .prefix = chans=            # will get prepended with no JSON-processing

        ..+.node = meanchansimage   # third file, just specify the node. Append will be same as last time
        .prefix = "mean chans image\\n" # will get prepended, but JSON-processed first.
        ..+.node = meanimage        # fourth file, just specify the node. Append will be same as last time
        """
        r.run(None, test)

        txt = open(out).read()
        # inspect.cleandoc will remove the leading whitespace from the string, so we can format it nicely here,
        # but it will also remove the trailing newline, so we add it back in.
        assert txt == inspect.cleandoc("""meanchans=[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]
            chans=0.45332±0.19508
            mean chans image
            [0.57216±0.16391, 0.3716±0.11629, 0.22292±0.080861]
            0.38889±0.19005
            """)+"\n"


def test_multiple_text_output_append_shorthand_from_file(globaldatadir):
    """Test that we can use the append option to add to a file when we're doing text output, using the "shorthand"
    that lets us use the previous filename and append mode by simply not specifying them.
    We also test output prefixes here and the idea that things in quotes will be unescaped using JSON.
    This time we read the test string from a file and use Jinja templating to set the input file."""

    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")

        r.run(globaldatadir / "runner/testscalars.params",
              data_for_template={"out": out, "globaldatadir": globaldatadir})

        txt = open(out).read()
        # inspect.cleandoc will remove the leading whitespace from the string, so we can format it nicely here,
        # but it will also remove the trailing newline, so we add it back in.

        # There is a LUDICROUSLY SMALL chance that this will fail if run very, very close to midnight! :)
        assert txt == inspect.cleandoc(f"""meanchans=[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]
            chans0=0.45332±0.19508
            mean chans image at {datetime.datetime.now().date().isoformat()}
            [0.57216±0.16391, 0.3716±0.11629, 0.22292±0.080861]
            0.38889±0.19005
            """)+"\n"

        # run again and check the count gets incremented.

        out = os.path.join(td, "output2.txt")
        r.run(globaldatadir / "runner/testscalars.params",
              data_for_template={"out": out, "globaldatadir": globaldatadir})
        txt = open(out).read()
        assert txt == inspect.cleandoc(f"""meanchans=[0.67498±0.11292, 0.43386±0.085651, 0.25112±0.060702]
            chans1=0.45332±0.19508
            mean chans image at {datetime.datetime.now().date().isoformat()}
            [0.57216±0.16391, 0.3716±0.11629, 0.22292±0.080861]
            0.38889±0.19005
            """)+"\n"

        # run again with a different file with slightly different data

        out = os.path.join(td, "output3.txt")
        r.run(globaldatadir / "runner/testscalars2.params",
              data_for_template={"out": out, "globaldatadir": globaldatadir})
        txt = open(out).read()
        assert txt == inspect.cleandoc(f"""meanchans=[1.125±0.18821, 0.7231±0.14275, 0.41853±0.10117]
            chans2=0.75553±0.32514
            mean chans image at {datetime.datetime.now().date().isoformat()} for test2.pcot with testscalars2.params
            [0.9536±0.27318, 0.61933±0.19381, 0.37154±0.13477]
            mean image for 2   0.64816±0.31675
            """)+"\n"


def test_spectrum(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")
        text = f"""
            multidot.rois.+circle.label = fish
            .croi.x = 100
            .y = 100
            .r = 30

            inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
            .itemname = image0
            outputs.+.file = {out}
            .clobber = y
            .node = spectrum
        """
        r.run(None,
              param_file_text=text,
              data_for_template={"out": out, "globaldatadir": globaldatadir})
        txt = open(out).read().strip() # remove trailing newline
        assert txt == inspect.cleandoc("""
        name,m640,s640,p640,m540,s540,p540,m440,s440,p440
        0,0.64584,0.07426,29,0.42077,0.05998,29,0.23643,0.03395,29
        1,0.79805,0.05037,29,0.5183,0.05628,29,0.31383,0.05833,29
        2,0.68998,0.08074,29,0.43359,0.06124,29,0.25298,0.04079,29
        3,0.72292,0.05138,29,0.44966,0.04938,29,0.24049,0.04406,29
        4,0.7445,0.06635,29,0.48617,0.05383,29,0.28073,0.04494,29
        fish,0.65038,0.10801,2821,0.41504,0.08667,2821,0.23329,0.06791,2821
        """)


def test_add_circle_to_multidot_using_list(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output.txt")
        text = f"""
            multidot.rois.+circle
            .label = fish
            .croi = [100, 150, 4]
            
            inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
            .itemname = image0
            
            outputs.+
            .file = {out}
            .clobber = y
            .node = spectrum
        """
        r.run(None,
              param_file_text=text,
              data_for_template={"out": out, "globaldatadir": globaldatadir})
        txt = open(out).read().strip() # remove trailing newline
        assert txt == inspect.cleandoc("""
        name,m640,s640,p640,m540,s540,p540,m440,s440,p440
        0,0.64584,0.07426,29,0.42077,0.05998,29,0.23643,0.03395,29
        1,0.79805,0.05037,29,0.5183,0.05628,29,0.31383,0.05833,29
        2,0.68998,0.08074,29,0.43359,0.06124,29,0.25298,0.04079,29
        3,0.72292,0.05138,29,0.44966,0.04938,29,0.24049,0.04406,29
        4,0.7445,0.06635,29,0.48617,0.05383,29,0.28073,0.04494,29
        fish,0.57056,0.16577,49,0.37397,0.12172,49,0.23904,0.08788,49
        """)


def test_run_modify_run(globaldatadir):
    """This tests that we can change an output file name and an input node and run again"""

    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out1 = os.path.join(td, "output1.txt")
        out2 = os.path.join(td, "output2.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out1}
        .node = mean
        run
        
        outputs.0.file = {out2}
        k.val = 2.4
        """
        r.run(None, test)

        txt = open(out1).read()
        assert txt == "0.45332±0.19508\n"
        txt = open(out2).read()
        assert txt == "0.90664±0.39016\n"   # double the previous value


def test_run_modify_with_reset_value_run(globaldatadir):
    """Test that the reset command does what it should - reset to the saved data.
    Here we reset an individual value in a node.
    """

    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out1 = os.path.join(td, "output1.txt")
        out2 = os.path.join(td, "output2.txt")
        out3 = os.path.join(td, "output3.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out1}
        .node = mean
        run

        outputs.0.file = {out2}
        k.val = 2.4
        run

        outputs.0.file = {out3}
        reset k.val
        run
        """
        r.run(None, test)

        txt = open(out1).read()
        assert txt == "0.45332±0.19508\n"
        txt = open(out2).read()
        assert txt == "0.90664±0.39016\n"  # double the previous value
        txt = open(out3).read()
        assert txt == "0.45332±0.19508\n"


def test_run_modify_with_reset_node_run(globaldatadir):
    """Test that the reset command does what it should - reset to the saved data.
    Here we reset a node.
    """

    pcot.setup()
    r = Runner(globaldatadir / "runner/test2.pcot")

    with tempfile.TemporaryDirectory() as td:
        out1 = os.path.join(td, "output1.txt")
        out2 = os.path.join(td, "output2.txt")
        out3 = os.path.join(td, "output3.txt")

        test = f"""
        inputs.0.parc.filename = {globaldatadir / 'parc/multi.parc'}
        .itemname = image0
        outputs.+.file = {out1}
        .node = mean
        run

        outputs.0.file = {out2}
        k.val = 2.4
        run

        outputs.0.file = {out3}
        reset k
        run
        """
        r.run(None, test)

        txt = open(out1).read()
        assert txt == "0.45332±0.19508\n"
        txt = open(out2).read()
        assert txt == "0.90664±0.39016\n"  # double the previous value
        txt = open(out3).read()
        assert txt == "0.45332±0.19508\n"
