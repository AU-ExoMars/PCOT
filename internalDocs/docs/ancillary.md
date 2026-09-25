# Ancillary data

Working notes (from 2026-09-25) on the ancillary data package (`src/pcot/ancillary/`), which attaches
extra data, such as exposure time, to the bands of an ImageCube. It reads the data from "sidecar" files
next to the image files (e.g. AUPE's `.png.xml`), or from the image data itself (ENVI, PDS4).
It will eventually replace the AUPE XML input method, which reads exposure times into a separate
vector whose elements have to be matched to bands by hand.

## To do

### Fixes to the current code

- [x] Register the AUPE loader: nothing imports `aupe.py` yet, so `LOADERS` stays empty. Import it
  from `ancillary/__init__.py` or from `pcot.setup()`. (Done: both - `pcot.setup()` imports the
  package before loading plugins, so built-in loaders are tried before plugin ones.)
- [x] Make `_load()` return `None` on any error, as `attempt_load()` promises. At the moment these
  can crash the whole multifile load:
    - [x] `ET.parse()` on malformed or unreadable XML
    - [x] `x.get("value")` returning `None`, which then fails on `.split()`
    - [x] `md["exposure_time"]` and `float(...)`, which aren't inside the `try` (the `try` only
      covers the split and zip, which can't really fail)
- [x] Log a warning when a sidecar file exists but can't be parsed, as opposed to there being no
  sidecar at all. Otherwise a broken file silently gives no exposure.
  (Done: loaders report problems to `multifile_loader()`, which logs a warning only if no loader
  could read the file, so a file in another loader's convention doesn't cause spurious warnings.)
- [x] Decide whether a sidecar with some fields but no `exposure_time` should still return the
  fields it does have, rather than being rejected entirely. (Done: yes. Fields are read from the
  `FIELDS` table in `ancillary/aupe.py`; missing fields are left out quietly, a field with a bad
  value is left out with a warning, and a file with none of the fields counts as unreadable so
  that other loaders get a chance.)

### Design questions

- [x] Key names and units: agree a set of standard keys (e.g. `exposure`) with documented units,
  and have each loader convert to them (AUPE's `0.009911` is presumably seconds; other cameras may
  use milliseconds). (Done: keys and units are defined once in `ancillary/keys.py` - still fluid,
  so loaders only ever refer to them through those constants. Exposure time is in seconds.)
- [x] Confirm the unit of AUPE3's `exposure_time`: the loader assumes seconds
  (`EXPOSURE_TIME_TO_SECONDS = 1.0` in `ancillary/aupe.py`). (Done: it's seconds.)
- [ ] Where the data lives on the ImageCube: per band, for the whole cube, or both. Keep it off
  `Source`, which may not stay attached to images in future.
- [ ] How it survives processing:
    - [ ] Carried through band-preserving operations: copies, ROI subimages and `modifyWithSub()`,
      crop, `a$640` band selection, merging bands
    - [ ] A rule for arithmetic between images (`a/b` etc.): drop it, or keep it only when both
      sides agree. Write the rule down before the code spreads through `imagecube.py`.
- [ ] Saving and loading: include it when ImageCubes are saved to `.pcot` documents and PARC
  archives.
- [ ] How users get at it: e.g. an `exposure(a)` datum function returning a vector with one value
  per band, as the direct replacement for the AUPE XML input.
- [ ] Inputs other than Multifile: ENVI and PDS4 carry this data in the files themselves, so decide
  how their readers feed into the same mechanism.

### Smaller things

- [ ] Docstring fixes in `ancillary/__init__.py`: "fiile" should be "file", and "support either
  data for the cube a whole" is missing "per-band data or ..." and an "as".
- [ ] Give `attempt_load()` a return type: `Optional[Dict[str, Any]]`.
- [ ] Tests: reuse the real AUPE file in `tests/data/aupexml/` (its `....png.xml` name matches the
  sidecar pattern), but give these tests their own copy, or move the file somewhere neutral, so
  removing AUPE XML doesn't take it with it.

### Retiring the AUPE XML input once this works

- [ ] Delete `aupeXMLmethod.py`, `inputaupexml.ui`, `tests/input/test_aupexml.py` and its data
  (unless the ancillary tests now use that data).
- [ ] Remove the import, the method-list entry and `AUPEXML = 7` from `inp.py`, and
  `setInputAUPEXML()` from `document.py`.
- [ ] Update the MEXICO CROSS release notes: the AUPE XML entry becomes the ancillary data feature,
  if AUPE XML never ships in a release.
- [ ] Nothing extra is needed for saved documents. Input methods are now saved by name (commit
  `d3ba5e09`), so documents saved with AUPE XML active will load with their exposure data kept as a
  fixed (Direct) input, plus a warning.
