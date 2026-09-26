# Ancillary data

Working notes (from 2026-09-25) on the ancillary data package (`src/pcot/ancillary/`), which attaches
extra data, such as exposure time, to the bands of an ImageCube. It reads the data from "sidecar" files
next to the image files (e.g. AUPE's `.png.xml`), or from the image data itself (ENVI, PDS4).
It will eventually replace the AUPE XML input method, which reads exposure times into a separate
vector whose elements have to be matched to bands by hand.

It's expected to be used sparingly - typically just normalising for exposure in an `expr` node with
something like `a/exposure(a)`. The overriding rule is the Law of Least Astonishment.

## Behaviour

- **Storage:** `ImageCube.ancillary` is a `BandAncillary` (`ancillary/bandancillary.py`): one dict
  per band, keyed by the names in `ancillary/keys.py`. A band with no data has an empty dict.
  There's no whole-cube storage yet: a value for the whole capture is stored in every band.
  Whole-cube storage can be added inside `BandAncillary` later without changing its users.
- **Not on `Source`:** it's deliberately separate from sources. Sources may not stay attached to
  images, and they're merged when images are combined (e.g. `a/b` unions each band's sources),
  which would produce meaningless ancillary data.
- **What it means:** ancillary data describes how the pixel data was acquired. So it's **kept** by
  operations which don't change pixel values (copies, crops, ROIs, band selection and reordering,
  geometric operations like rotate/flip/resize, and changes to DQ bits or uncertainty only), and
  **dropped** by operations which do (arithmetic, functions, most nodes). For example, the result of
  `a/exposure(a)` has no exposure data, so correcting it a second time can't happen by accident.
- **Dropped by default:** `ImageCube(...)` without an `ancillary` argument gives every band empty
  data, so any code which hasn't been deliberately updated drops it rather than passing on something
  wrong. `BandAncillary` mirrors `MultiBandSource`'s API (`select()`, `concat()`, `copy()`), so code
  which rearranges bands can do the same to both.
- **Missing data should be an error:** e.g. `exposure(a)` on an image without exposure data should
  raise a clear error, not return a made-up value.
- **Currently implemented:** the constructor (and its band-count check), `copy()` and
  `shallowCopy()` (so `rotate()`/`flip()` too) keep it; `modifyWithSub()` drops it when writing new
  pixels but keeps it for DQ/uncertainty-only changes; `zeros_like()` drops it. Band selection keeps
  the selected bands' data: `getChannelImageByFilter()` (so `a$640`, `a$name`, `a$N` and `a[...]`)
  and `rgbImage()` (so `rgb()`). Crops and resizes keep it: `cropROI()` (so the *crop* node),
  `cropother()`, `resize()` and the `crop()` function. `merge()` concatenates the images' data, with
  no data for bands made from numbers. `nominal()` (which only strips uncertainty), the *offset* node
  (which only shifts the image) and the registration nodes (*tvl1 autoreg* and *manual register*,
  which warp the moving image and, for *manual register*, shift the fixed one) keep each image's own
  data.
- **Values must be JSON-serialisable:** values are typed as `Any`, but they're saved as-is in
  documents and PARC archives, so they must be `str`, `int`, `float`, `bool`, `None`, or lists/dicts
  of those (not numpy scalars). Anything else makes saving fail, with an error from the archive code
  naming the offending item.
- **Saving:** `ImageCube.serialise()` saves it under an `ancillary` key. Images saved before
  ancillary data existed have no such key, and load with empty data for every band; older PCOT
  versions ignore the key.
- **Where it comes from:** the Multifile loader (`load.multifile()`) calls `multifile_loader()` for
  each band's file, so each band gets the data from its own sidecar, in the same order as the bands.
  A band with no sidecar gets no data.

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
- [x] Where the data lives on the ImageCube: per band, for the whole cube, or both. Keep it off
  `Source`, which may not stay attached to images in future. (Done: per band, in `BandAncillary` -
  see Behaviour above.)
- [x] How it survives processing:
    - [x] Carried through operations which don't change pixel values: copies, rotate/flip,
      DQ/uncertainty-only `modifyWithSub()`, band selection, crops, resize and merge (see
      "Currently implemented" above).
    - [x] Decide about the remaining operations which don't change pixel values but still drop
      it: `nominal()` (only strips uncertainty - probably keep), the *offset* node (only shifts the
      image - probably keep), and the registration nodes (warp one image onto another - arguably
      geometric like `resize()`). (Done: all keep it.)
    - [x] A rule for arithmetic between images (`a/b` etc.): drop it, or keep it only when both
      sides agree. Write the rule down before the code spreads through `imagecube.py`. (Done: drop
      it - see Behaviour above. Happens automatically, because arithmetic goes through
      `modifyWithSub()`.)
- [x] Saving and loading: include it when ImageCubes are saved to `.pcot` documents and PARC
  archives. (Done - see Behaviour above.)
- [x] How users get at it: e.g. an `exposure(a)` datum function returning a vector with one value
  per band, as the direct replacement for the AUPE XML input. It should raise a clear error if any
  band has no exposure data. (Done: `exposure()` in `datumfuncs.py` returns seconds, and raises an
  error naming the bands with no data, or saying the image has none.)
- [x] Inputs other than Multifile: ENVI and PDS4 carry this data in the files themselves, so decide
  how their readers feed into the same mechanism.
    - [x] ENVI: the reader reads the (non-standard) `exposure times` header field, in seconds, into
      each band's ancillary data. The writer writes it exactly, and omits the field if any band's
      exposure is unknown, rather than making values up. ENVI files are often already normalised
      for exposure (e.g. DN/s), so `exposure()`'s docstring warns that dividing by it again could
      be an error - the data is still read for information. ENVI files written by PCOT before
      this change contain placeholder exposures of 0.01, which will now be read as real.
    - [x] PDS4: `PDS4ImageProduct` reads each product's `exposure_duration` from its label (in
      seconds - the labels say `unit="s"`, but the unit isn't checked) and saves it in
      `serialise()`/`deserialise()`. A label without it, or a product saved before this, gives no
      exposure for that band rather than an error. PDS4 products (spec-rad) are already normalised
      for exposure, like ENVI, so `exposure()`'s docstring warns against dividing by it again.
      PCOT only reads PDS4, never writes it, so there's no writer side.

### Smaller things

- [x] Docstring fixes in `ancillary/__init__.py`: "fiile" should be "file", and "support either
  data for the cube a whole" is missing "per-band data or ..." and an "as".
- [x] Give `attempt_load()` a return type: `Optional[Dict[str, Any]]`.
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
