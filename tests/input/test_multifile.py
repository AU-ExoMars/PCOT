"""Multifile input tests"""
import pcot
from pcot.dataformats.raw import RawLoader
from pcot.datum import Datum
from pcot.document import Document
from pcot.inputs.multifile import presetModel, MultifileInputMethod
from fixtures import *


def test_multifile_load_with_default_pattern(globaldatadir):
    """Load up a set of images using the default filter pattern, which will give duff sources"""
    pcot.setup()
    doc = Document()

    # having created a document, set an input. Try one that doesn't exist first.
    v = doc.setInputMulti(0, str(globaldatadir / "dirdoesntexist"), ["1.png", "2.png", "3.png", "4.png"])
    assert v.startswith('Cannot read file')
    v = doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "zzzz2.png", "32768.png", "65535.png"])
    assert v.startswith('Cannot read file') and 'zzzz2' in v
    # this won't load because of a size mismatch
    v = doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "32768.png", "65535.png", "wrongsize.png"])
    assert v == "all images must be the same size in a multifile"

    # this should load, but the sources are going to be a complete mess.
    names = ["0.png", "32768.png", "65535.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), names) is None

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 32768 / 65535, 1))

    # check the sources, such as they are
    assert len(img.sources) == 3
    for i, sourceSet in enumerate(img.sources):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        print(s.long())
        # if we haven't got a good regex to extract the filter data, multifile will extract dummy data.
        assert f.cwl == 0
        assert f.fwhm == 0
        assert f.name == '??'
        assert f.position == '??'
        assert f.transmission == 1
        path = str(globaldatadir / "multi" / names[i])
        # starts with zero because this is for input 0
        assert s.long() == f"0: Cam: None, Filter: ??(0nm) pos=?? desc=None resp=sim,3300 ext={path}"


def test_multifile_load_with_bad_pattern(globaldatadir):
    """Load up a set of images using a uncompilable pattern"""
    pcot.setup()
    doc = Document()

    # this should load, but the sources are going to be a complete mess, and the filter pattern is hopeless.
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "32768.png", "65535.png"],
                             filterpat='[') is None

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 32768 / 65535, 1))

    for sourceSet in img.sources:
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == 0
        assert f.fwhm == 0
        assert f.name == '??'
        assert f.position == '??'
        assert f.transmission == 1


def test_multifile_load_with_good_pattern(globaldatadir):
    """Here we set up a custom pattern to work out filter positions from file names, assuming that these are PANCAM
    filters."""
    pcot.setup()
    doc = Document()

    # The pattern is things like ...FilterL09.. for filter left-9.
    filenames = ["FilterL02.png", "TestFilterL01image.png", "FilterR10.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"),
                             filenames,
                             filterpat=r'.*Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*') is None

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (32768 / 65535, 0, 1))

    path = globaldatadir / "multi"

    # pancam filters L02, L01, R10.
    for sourceSet, pos, name, cwl, fwhm, trans, fn in zip(img.sources,
                                                        ('L02', 'L01', 'R10'),
                                                        ('G03', 'G04', 'S03'),
                                                        (530, 570, 450),
                                                        (15, 12, 5),
                                                        (0.957, 0.989, 0.000001356),
                                                        filenames,
                                                      ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == trans
        qq = s.long()
        # the long string here is a bit weird, in that it has the filenames for all the filters in always,
        # but that's because we're using the long string for the multifile input as a whole.
        assert s.long() == f"0: Cam: PANCAM, Filter: {name}({float(cwl)}nm) pos={pos} desc=None resp=sim,3300 ext={path / fn}"


def test_multifile_load_with_cwl(globaldatadir):
    pcot.setup()
    doc = Document()

    # This looks for a wavelength
    names = ["F740.png", "F780.png", "F840.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"),
                             names,
                             filterpat=r'.*F(?P<cwl>[0-9]+).*') is None

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 1, 32768 / 65535))

    for sourceSet, pos, name, cwl, fwhm, trans in zip(img.sources,                  # PANCAM filter set:
                                                          ('R03', 'R02', 'R01'),        # positions
                                                          ('G07', 'G08', 'G09'),      # names
                                                          (740, 780, 840),              # cwls
                                                          (15, 20, 25),                # fwhms
                                                          (0.983, 0.981, 0.989),        # transmission ratios
                                                          ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == trans


def test_multifile_raw(globaldatadir):
    pcot.setup()
    doc = Document()


    names=["240220_171254_Training Model-R02_+237_265ms.bin",
        "240220_171315_Training Model-R03_+239_212ms.bin",
        "240220_171234_Training Model-R01_+237_645ms.bin"]

    loader = RawLoader(format=RawLoader.UINT16,
                    width=1024, height=1024,
                    bigendian=True,
                    offset=48,
                    rot=90)

    assert doc.setInputMulti(0, str(globaldatadir / "multi/raw"),
                             names,
                             camera="TRAINING_GEOLOGY",
                             rawloader=loader,
                             bitdepth=10,
                             filterpat=r'.*Model-(?P<lens>L|R)(?P<n>[0-9][0-9]).*') is None

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    for sourceSet, pos, name, cwl, fwhm, trans in zip(img.sources,                  # TRAINING_GEOL filter set:
                                                          ('R02', 'R03', 'R01'),        # positions
                                                          ('G03', 'G04', 'G01'),      # names
                                                          (530, 570, 440),              # cwls
                                                          (15, 12, 25),                # fwhms
                                                          (0.957, 0.989, 0.987),        # transmission ratios
                                                          ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == trans

        # check a pixel we know is "bright" (although
        bands = img[768,662]
        assert bands[0].n > 0.92
        assert bands[1].n > 0.78
        assert bands[2].n > 0.92

        assert bands[0].u == 0
        assert bands[0].dq == dq.NOUNCERTAINTY
        assert bands[1].u == 0
        assert bands[1].dq == dq.NOUNCERTAINTY
        assert bands[2].u == 0
        assert bands[2].dq == dq.NOUNCERTAINTY


def test_multifile_save_falls_back_to_last_good_data_when_unreadable(globaldatadir):
    """If a multifile input's cached data has been invalidated and can no longer be
    re-read (e.g. because a parameter change broke it, or the source vanished after
    the last successful read), saving the document should still persist the last
    successfully-loaded data rather than silently saving nothing for that input."""
    pcot.setup()
    doc = Document()

    names = ["0.png", "32768.png", "65535.png"]
    # setInputMulti() forces an eager read, so this also populates lastGoodData
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), names) is None

    inp = doc.inputMgr.getInput(0)
    method = inp.getActive()
    assert not method.data.isNone()
    assert not method.lastGoodData.isNone()

    # break it: add a mismatched-size file, so the next reload will raise even though
    # the directory and existing files are all still present; then invalidate so a
    # reload is actually attempted (the source isn't "missing" so this isn't a no-op)
    method.files = names + ["wrongsize.png"]
    method.invalidate()
    assert method.missingPathReason() is None
    assert method.data.isNone()

    out = inp.serialise(internal=False, saveInputs=True)

    # the live method itself really is broken now
    assert method.data.isNone()
    # but the serialised data still has the last known-good image
    assert out['activeData'] is not None
    restored = Datum.deserialise(out['activeData'])
    assert restored.isImage()
    assert restored.val.channels == 3


def test_multifile_save_does_not_reset_mapping(globaldatadir):
    """readData() used to unconditionally reset the RGB channel mapping ("reguess") on every
    call. That meant a reload triggered purely to serialise data for saving (e.g. because the
    method was left invalidated from an earlier change) would silently reset the user's chosen
    channel mapping as a side effect of Save. The reguess should only happen when the method is
    actually invalidated for a real reason, not on every readData()."""
    pcot.setup()
    doc = Document()

    names = ["0.png", "32768.png", "65535.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), names) is None

    inp = doc.inputMgr.getInput(0)
    method = inp.getActive()
    assert not method.data.isNone()

    # simulate the user having picked a specific (non-guessed) channel mapping
    method.mapping.set(2, 1, 0)

    # break it exactly as in the fallback test above, but WITHOUT calling invalidate()
    # again afterwards - self.data is already null from setInputMulti()'s internal
    # invalidate(), so this reload attempt is only triggered by serialise()/get() below,
    # not by any fresh "something changed" event.
    method.files = names + ["wrongsize.png"]
    method.invalidate()
    assert method.mapping.red == -1  # invalidate() itself does force a reguess...

    # ...so re-set it to simulate a plain reload attempt (e.g. via save) happening after
    # the mapping had already been (re)established some other way
    method.mapping.set(2, 1, 0)

    inp.serialise(internal=False, saveInputs=True)

    # readData() ran (and failed) as part of that serialise(), but should not have
    # touched the mapping
    assert method.mapping.red == 2
    assert method.mapping.green == 1
    assert method.mapping.blue == 0


def test_multifile_preset_apply_legacy_and_missing_fields():
    """MultifileInputMethod.applyPreset() is the single canonical implementation used by
    the GUI widget, the parameter-file path and the scripting load.multifile() path.
    Check it tolerates presets which predate 'bitdepth'/'leftjustified' (older presets)
    and which use the legacy 'filterset' key instead of 'camera' (very old presets)."""
    pcot.setup()

    loader = RawLoader(format=RawLoader.UINT16, width=16, height=32)
    preset = {
        'rawloader': loader.serialise(),
        'filterpat': '.*Test-(L|R)(?P<pos>[0-9][0-9]).*',
        'filterset': 'AUPE_LEFT_NOCALIB',  # legacy key, not 'camera'
        # bitdepth/leftjustified deliberately omitted, as in presets saved before
        # those fields existed
    }

    m = MultifileInputMethod(None)
    m.applyPreset(preset)

    assert m.camera == 'AUPE_LEFT_NOCALIB'
    assert m.filterpat == '.*Test-(L|R)(?P<pos>[0-9][0-9]).*'
    assert m.bitdepth is None
    assert m.leftjustified is False
    assert m.rawLoader.format == RawLoader.UINT16
    assert m.rawLoader.width == 16
    assert m.rawLoader.height == 32

    # fetchPreset() should round-trip the now-normalised values (using 'camera', not
    # 'filterset', since that's the current key)
    fetched = m.fetchPreset()
    assert fetched['camera'] == 'AUPE_LEFT_NOCALIB'
    assert fetched['bitdepth'] is None
    assert fetched['leftjustified'] is False


def test_preset_model_load_by_name_is_a_pure_fetch():
    """PresetModel.loadPresetByName() must not apply the preset to anything or have any
    other side effect - it should be safe to call repeatedly. This guards against the
    double-apply bug class where a caller (dataformats.load.multifile()) used to invoke
    applyPreset() a second time with the (None) return value of a method that had
    already applied the preset itself."""
    loader = RawLoader(format=RawLoader.UINT8, width=8, height=8)
    preset = {
        'rawloader': loader.serialise(),
        'filterpat': '.*',
        'camera': 'AUPE_LEFT_NOCALIB',
    }
    presetModel.addPreset("puretest", preset)

    first = presetModel.loadPresetByName("puretest")
    second = presetModel.loadPresetByName("puretest")
    assert first == second == preset