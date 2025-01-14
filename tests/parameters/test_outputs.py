"""
Tests for the output mechanism of the Runner class - i.e. the outputs of the batch system.
"""

import tempfile

import pcot
from fixtures import *
from pcot.parameters.runner import Runner


def test_write_text_number_to_image_filename(globaldatadir):
    """It's actually OK to write a number to an image filename - it will be converted to a string, of course,
    but it's a bit of a weird thing to do. This test is just to check that it works. Otherwise I could add a check
    that we're not trying to write to an image format filename, but that seems (a) unnecessary and (b) hard to define
    (has anyone got a list of all image formats?)."""
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.png")

        test = f"""
        # run without changes
        outputs.+.file = {out}
        .node = mean(a)
        """

        r.run(None, test)

        txt = open(out).read()
        assert txt == "[0.15516±0.023474, 0.51942±0.079119, 0.54824±0.012403]\n"


def test_write_number_to_parc(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.parc")

        test = f"""
        # run without changes
        outputs.+.file = {out}
        .format = parc
        .node = mean(a)
        """

        r.run(None, test)

        txt = open(out).read()
        # standard viridis default will be fairly cyan
        assert txt == "[0.15516±0.023474, 0.51942±0.079119, 0.54824±0.012403]\n"
