"""
Tests for the output mechanism of the Runner class - i.e. the outputs of the batch system.
"""

import tempfile

import pcot
from fixtures import *
from pcot.parameters.runner import Runner


def test_cannot_write_text_number_to_image_filename(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.png")

        test = f"""
        # run without changes
        outputs.+.file = {out}
        .node = mean(a)
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Cannot write non-image data to an image file" in str(e)


def test_cannot_write_number_to_parc(globaldatadir):
    """Here we try to a numeric datum to a PARC file, which (at the moment) isn't allowed -
    batch files can only write image data to PARC. If you want to do that, you can do it
    in a script."""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.parc")

        test = f"""
        outputs.+.file = {out}
        .node = mean(a)
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Cannot write default format (text) data to a PARC file" in str(e)


def test_cannot_write_image_to_txt(globaldatadir):
    """Here we try to write an image to a text file, which (at the moment) isn't allowed -
    batch files can only write text data to text files. If you want to do that, you can do it
    in a script."""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.txt")

        test = f"""
        outputs.+.file = {out}
        .node = gradient
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Unsupported file format for image save: txt" in str(e)


def test_desc_must_be_none_for_nonparc_text(globaldatadir):
    """Cannot have a description on a non-PARC, and here it's a text anyway"""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.txt")

        test = f"""
        outputs.+.file = {out}
        .description = This is a description
        .node = gradient
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Description is not supported for image formats other than PARC" in str(e)


def test_desc_must_be_none_for_nonparc_image(globaldatadir):
    """Cannot have a description on a non-PARC image"""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.png")

        test = f"""
        outputs.+.file = {out}
        .description = This is a description
        .node = gradient
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Description is not supported for image formats other than PARC" in str(e)


def test_cannot_append_non_parc_images(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.png")

        test = f"""
        outputs.+.file = {out}
        .node = gradient
        run         # first run
        outputs[0].file = {out}
        .append = y # second run should fail
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Append is not supported for image formats other than PARC" in str(e)


def test_format_or_extension_provided_for_images(globaldatadir):
    """Got to have a format or extension for images"""
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1")

        test = f"""
        outputs.+.file = {out}
        .node = gradient
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "No extension provided in filename" in str(e)


def test_explicit_image_format(globaldatadir):
    """Can specify a format if an extension isn't given on an image; format will be added to the filename
    as a new extension"""
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1")

        test = f"""
        outputs.+.file = {out}
        .node = gradient
        .format = png
        """

        r.run(None, test)

        # try to open the image file
        from PIL import Image
        with Image.open(out+".png") as im:
            assert im.size == (1000, 1000)   # 1000 is the default size for export with annotations
            assert im.format == "PNG"
        im.close()


def test_cannot_specify_format_on_nonimage(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1")

        test = f"""
        outputs.+.file = {out}
        .node = mean(a)
        .format = png
        """

        with pytest.raises(ValueError) as e:
            r.run(None, test)
        assert "Cannot specify format for text output" in str(e)
