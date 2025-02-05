"""
Tests for the output mechanism of the Runner class - i.e. the outputs of the batch system.
"""

import tempfile
import datetime

import pcot
from tests.fixtures import *
from pcot.datum import Datum
from pcot.document import Document
from pcot.parameters.runner import Runner
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore
import pcot.datumfuncs as df


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
        with Image.open(out + ".png") as im:
            assert im.size == (1000, 1000)  # 1000 is the default size for export with annotations
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


def test_parc_image_write(globaldatadir):
    """Test we can write a single image to a PARC with a description"""
    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.parc")

        test = f"""
        outputs.+.file = {out}
        .annotations = n    # annotations not supported in PARC
        .node = striproi(a,1)
        .name = main
        .description = This is a description
        """

        r.run(None, test)

        # don't try to open the archive, just create an object for it. If we open it, we'll
        # get into trouble when we try to read - opening the archive is done during the the read.
        s = DatumStore(FileArchive(out))
        manifest = s.getManifest()
        assert len(manifest) == 1
        meta = s.getMetadata("main")
        assert manifest["main"] == meta  # checking the manifest is correct for 1 item

        assert meta.description == "This is a description"
        assert meta.datumtype == Datum.IMG.name

        # make sure it was created recently
        now = datetime.datetime.now()
        assert meta.created < now
        interval = (now - meta.created).total_seconds()
        assert interval < 2

        # now get the image - we need a document so that we can reconstruct image sources
        doc = Document()
        imgd = s.get("main", doc)
        assert imgd is not None
        assert isinstance(imgd, Datum)
        img = imgd.get(Datum.IMG)
        assert img is not None
        # check the basic parameters are OK
        assert img.w == 256
        assert img.h == 256
        assert img.channels == 3

        # now check some property of the image - in this case we check the mean
        # of the result, which we got the ground truth for by running the application.
        v = df.mean(imgd).get(Datum.NUMBER)
        assert str(v) == "[0.4557±0.15167, 0.47677±0.13817, 0.47621±0.13479]"


def test_parc_multi(globaldatadir):
    """Test we can add multiple images to a PARC file"""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.parc")

        # in this test we're going to write multiple outputs in a single run

        test = f"""
        outputs.+.file = {out}
        .annotations = n    # annotations not supported in PARC
        .node = striproi(a,1)
        .name = main
        .description = Primary output image
        
        # we're missing out the file and the annotations; they should be copied from the previous output
        ..+.append = y
        .node = test1
        .name = testimg1
        .description = Test image 1
        
        # we can miss out append here, it will be copied from the previous output
        ..+.node = test2
        .name = testimg2
        .description = Test image 2
        
        ..+.node = test3
        .name = testimg3
        .description = Test image 3, with 4 channels
        """

        r.run(None, test)
        s = DatumStore(FileArchive(out))

        assert(len(s.getManifest()) == 4)   # there are four lights! Sorry, files!

        doc = Document()        # need a document as context

        imgd = s.get("main", doc)
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.w == 256
        assert img.h == 256
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.47677±0.13817, 0.47621±0.13479]"

        # test1 mean is [0.31899±0.10617, 0.47677±0.13817, 0.47621±0.13479]
        # test2 mean is [0.4557±0.15167, 0.095353±0.027633, 0.47621±0.13479]
        # test3 mean is [0.4557±0.15167, 0.47677±0.13817, 0.23811±0.067394, 0.93246±0.27525]

        imgd = s.get("testimg1", doc)
        assert s.getMetadata("testimg1").description == "Test image 1"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.31899±0.10617, 0.47677±0.13817, 0.47621±0.13479]"

        imgd = s.get("testimg2", doc)
        assert s.getMetadata("testimg2").description == "Test image 2"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.095353±0.027633, 0.47621±0.13479]"

        imgd = s.get("testimg3", doc)
        assert s.getMetadata("testimg3").description == "Test image 3, with 4 channels"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 4
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.47677±0.13817, 0.23811±0.067394, 0.93246±0.27525]"


def test_parc_multi_jinja_multi_run(globaldatadir):
    """Add a bunch of files to a PARC archive using a loop in a Jinja template, and doing multiple
    run commands in that loop. Also tests that if the last command in the loop is a run, the implied
    end-of-file run is not added."""

    pcot.setup()
    r = Runner(globaldatadir / "runner/gradient.pcot")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "output1.parc")
        # note that we're also passing the filename into Jinja rather than using an f-string, and we're
        # using multiple runs to add the files

        test = """
        outputs.+.file = {{out}}
        .annotations = n    # annotations not supported in PARC
        .node = striproi(a,1)
        .name = main
        .description = Primary output image
        run
        
        {% for i in range(1,4) %}       # values 1,2,3
            # just one output, keep the same file and settings but append.
            outputs.0.append = y
            .node = test{{i}}
            .name = testimg{{i}}
            .description = Test image {{i}}
            run
        {% endfor %}
        # normally a "run" is appended, but this won't happen if the previous command was also a "run", which
        # it will be here.
        """

        r.run(None, test, data_for_template={"out": out})

        s = DatumStore(FileArchive(out))
        assert(len(s.getManifest()) == 4)

        doc = Document()        # need a document as context

        # now do essentially the same tests as we did in the previous test, with a slight change for
        # test 3 because the description is different.

        imgd = s.get("main", doc)
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.w == 256
        assert img.h == 256
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.47677±0.13817, 0.47621±0.13479]"

        # test1 mean is [0.31899±0.10617, 0.47677±0.13817, 0.47621±0.13479]
        # test2 mean is [0.4557±0.15167, 0.095353±0.027633, 0.47621±0.13479]
        # test3 mean is [0.4557±0.15167, 0.47677±0.13817, 0.23811±0.067394, 0.93246±0.27525]

        imgd = s.get("testimg1", doc)
        assert s.getMetadata("testimg1").description == "Test image 1"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.31899±0.10617, 0.47677±0.13817, 0.47621±0.13479]"

        imgd = s.get("testimg2", doc)
        assert s.getMetadata("testimg2").description == "Test image 2"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 3
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.095353±0.027633, 0.47621±0.13479]"

        imgd = s.get("testimg3", doc)
        assert s.getMetadata("testimg3").description == "Test image 3"
        img = imgd.get(Datum.IMG)
        assert img is not None
        assert img.channels == 4
        mean = df.mean(imgd).get(Datum.NUMBER)
        assert str(mean) == "[0.4557±0.15167, 0.47677±0.13817, 0.23811±0.067394, 0.93246±0.27525]"
