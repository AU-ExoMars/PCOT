import errno
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict

import numpy as np
from proctools.products import DataProduct

import pcot.config
from pcot import ui
from pcot.cameras import getFilter
from pcot.dataformats.pds4 import ProductList
from pcot.dataformats.raw import RawLoader
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping, ImageCube, load_rgb_image
from pcot.sources import StringExternal, MultiBandSource, Source
from pcot.utils import image
from pcot.utils.datumstore import readParc

logger = logging.getLogger(__name__)


def rgb(fname: str|Path, inpidx: int = None, mapping: ChannelMapping = None,
        debayer_algo:str = 'NONE', debayer_pattern: str = None, camera=None, neg_method="Leave") -> Datum:
    """Load an imagecube from an RGB file (png, jpeg etc.)

    - fname: the filename
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    - debayer_algo: None, or "None" or a debayering algorithm (see pcot.utils.demosaicing). If
      the image is multiband, only the first band will be used.
    - debayer_pattern: the pattern of the pixels for debayering (see pcot.utils.demosaicing).
    - camera: the camera, which must have R, G and B filters.
    - neg_method: "Leave" to leave untouched, otherwise one of NEGATIVE_PROCESSING_METHODS (see pcot.utils.demosaicing)

    """

    if camera is None:
        e = StringExternal("RGB", str(fname))
        sources = MultiBandSource([
            Source().setBand("R").setExternal(e).setInputIdx(inpidx),
            Source().setBand("G").setExternal(e).setInputIdx(inpidx),
            Source().setBand("B").setExternal(e).setInputIdx(inpidx),
        ])
    else:
        import pcot.cameras
        cam = pcot.cameras.getCamera(camera)
        r = cam.getFilter("R")
        g = cam.getFilter("G")
        b = cam.getFilter("B")
        e = StringExternal(camera, fname)
        sources = MultiBandSource([
            Source().setBand(r).setExternal(e).setInputIdx(inpidx),
            Source().setBand(g).setExternal(e).setInputIdx(inpidx),
            Source().setBand(b).setExternal(e).setInputIdx(inpidx),
        ])




    # this can throw an exception if the file is not found
    img = ImageCube.load(fname, mapping, sources, debayer_algo=debayer_algo, debayer_pattern=debayer_pattern,
                         neg_method = neg_method)
    return Datum(Datum.IMG, img)


def envi(fname: str|Path, inpidx: int = None, mapping: ChannelMapping = None) -> Datum:
    """Load an imagecube from an ENVI file

    - fname: the name of the .hdr (header) file - the .dat (data) file must be in the same directory
      and have the same name (except for the extension)
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    """

    from pcot.dataformats.envi import load

    h, img = load(fname)

    # construct the source data
    e = StringExternal("ENVI", f"ENVI:{str(fname)}")
    sources = [Source().setBand(f).setExternal(e).setInputIdx(inpidx) for f in h.filters]
    sources = MultiBandSource(sources)
    if mapping is None:
        mapping = ChannelMapping()
    if h.defaultBands is not None:
        mapping.set(*h.defaultBands)
        img = ImageCube(img, mapping, sources, defaultMapping=mapping.copy())
    else:
        img = ImageCube(img, mapping, sources)

    return Datum(Datum.IMG, img)


def multifile(directory: Path|str,
              fnames: List[str],
              preset: Optional[str] = None,
              filterpat: str = None,
              bitdepth: int = None,
              leftjustified: bool = False,
              camera: str = None,
              rawloader: Optional[RawLoader] = None,
              inpidx: int = None,
              mapping: ChannelMapping = None,
              cache: Dict[str, Tuple[np.ndarray, float]] = None,
              really_no_camera: bool = False,
              dn_ranges: Optional[Dict[str, Tuple[float, float]]] = None) -> Datum:
    """Load an imagecube from multiple files (e.g. a directory of .png files),
    where each file is a monochrome image of a different band. The names of
    the filters for each band are derived from the filenames using the filterpat
    regular expression pattern. The filter set specifies which table is used
    to look up the filter names.

    Many of the settings can be left as None, in which case defaults are used, but if a preset
    is used, then the settings in the preset will override the defaults.

    - directory: the directory containing the files
    - fnames: the list of filenames
    - preset - the name of the preset to use or None if not using a preset. Presets are created using
      the multifile input method in the UI and are stored in a file in the user's home directory.
      Other settings passed into this function will override the settings in the preset.
    - filterpat: a regular expression pattern that extracts the filter name from the filename
    - bitdepth: how many bits are actually used in the image - we divide by 2^bitdepth-1 to normalise. If none,
        we use the "nominal" depth (8 or 16).
    - leftjustified: if True, the significant bits given by bitdepth are assumed to occupy the top of
        their container (e.g. a 10-bit value stored in the top of a 16-bit word, with the bottom 6 bits
        always zero) rather than the bottom. Has no effect if bitdepth is None.
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    - camera: the name of the camera to use for filter name lookup etc. If not set or None, default camera is used
      (but see really_no_camera)
    - rawloader: a RawLoader object to use for loading raw files (unused if we're not loading raw files)
    - cache: a dictionary of cached data to avoid loading the same file multiple times.
      The key is the filename and the value is a tuple of the image data and the time it was loaded.
    - really_no_camera: really set the camera to None! This is used when we are just loading images with no regard to band etc.
    - dn_ranges: optional dict; if supplied it will be populated (keyed by the entries of fnames) with a
      (dn_min, dn_max) tuple per successfully-loaded file, recording its raw pixel value range before
      scaling. Purely a side-channel for UI display - doesn't affect the returned Datum, and files that
      raise before loading simply get no entry.

    The regular expression works thus:
        - If the filterpat contains ?P<lens> and ?P<n>, then lens+n is used to look up the filter by position.
          For example lens=L and n=01 would look up L01 in the filter position
        - If the filterpat contains just ?P<pos>, then pos is used to look up the filter by position.
        - Otherwise if the filterpat contains ?P<name>, then name is used to look up the filter by name.
        - Otherwise if the filterpat contains ?P<cwl>, then cwl is used to look up the filter's wavelength.
        - If these all fail, a "dummy" filter is used.

    an example:

        `.*[LR]WAC(?P<pos>[0-9][0-9]).*`
        - `.*` matches any characters
        - `[LR]]` matches L or R
        - `WAC` matches "WAC" (Wide Angle Camera)
        - `(?P<pos>[0-9][0-9])` matches two digits and assigns them to the pos group
        - `.*` matches any characters

    So for a filename like "Set18_LWAC01.png", the filter position would be "01".

    A second example where the position is split into "lens" and "n":

        `.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*`

        - `.*` matches any characters
        - `(?P<lens>L|R)` matches L or R and assigns it to the lens group
        - `WAC` matches "WAC" (Wide Angle Camera)
        - `(?P<n>[0-9][0-9])` matches two digits and assigns them to the n group
        - `.*` matches any characters

    Here, for a filename like "Set18_LWAC01.png", the filter position would be "L01".


    """

    # NB: these two imports are kept local (not at module level) because
    # pcot.inputs.multifile imports pcot.dataformats.load at module level - a top-level
    # import here would be circular.
    from pcot.inputs.multifile import presetModel, MultifileInputMethod
    logger.debug(f"Multifile load from directory {str(directory)} at bitdepth {bitdepth}")
    if rawloader is None:
        # preset handling (ALL fields, not just rawloader) only happens when the caller
        # hasn't already supplied an explicit rawloader - preserves existing behaviour
        # where passing rawloader= bypasses preset lookup entirely.
        if preset is not None:
            # Throwaway "orphan" MultifileInputMethod (inp=None is an explicitly supported
            # use - see InputMethod.__init__) purely to reuse the canonical applyPreset()
            # instead of re-declaring the multifile preset field list here.
            presetHolder = MultifileInputMethod(None)
            presetHolder.applyPreset(presetModel.loadPresetByName(preset))
            # merge: explicit args passed into this function win over the preset - opposite
            # precedence to MultifileInputMethod.modifyWithParameterDict's preset-then-
            # override, deliberately so, since this is the "convenience defaults" scripting
            # entry point.
            camera = camera or presetHolder.camera
            filterpat = filterpat or presetHolder.filterpat
            bitdepth = bitdepth or presetHolder.bitdepth
            leftjustified = leftjustified or presetHolder.leftjustified
            rawloader = presetHolder.rawLoader

        filterpat = filterpat or pcot.config.data.multifile_pattern
        if really_no_camera:
            camera = None
        else:
            camera = camera or pcot.config.data.default_camera

    def getFilterSearchParam(p) -> Tuple[Optional[Union[str, int]], Optional[str]]:
        """Returns the thing to search for to match a filter to a path and the type of the search"""

        if filterre is None or camera is None:
            return None, None
        else:
            m = filterre.match(p)
            if m is None:
                ui.error(f"Multifile loader cannot get filter from pattern: {p}, regex {filterre.pattern}")
                return None, None
        
            m = m.groupdict()
            if '<lens>' in filterpat:
                if '<n>' not in filterpat:
                    raise Exception(f"A filter pattern with 'lens' must also have 'n'")
                # lens is either left or right
                lens = m.get('lens', '')
                n = m.get('n', '')
                return lens + n, 'pos'
            elif '<pos>' in filterpat:
                return m.get('pos', ''), 'pos'
            elif '<name>' in filterpat:
                return m.get('name', ''), 'name'
            elif '<cwl>' in filterpat:
                return int(m.get('cwl', '0')), 'cwl'
            else:
                ui.error(f"Multifile loader pattern: bad pattern {camera} {filterre}, need at least one of <name>, <pos>, <cwl>")
                return None, None

    # first compile the regex
    import re
    try:
        filterre = re.compile(filterpat)
    except re.error as e:
        ui.error(f"Error in filter pattern: {e}")
        filterre = None

    sources = []  # array of source sets for each image
    imgs = []  # array of actual images (greyscale, numpy)

    # make sure we're dealing with a Path
    directory = Path(directory)

    # load each image - they must all be the same size and will be converted
    # to greyscale

    for fname in fnames:
        if fname is not None:
            # we use the relative path here, it's more right that using the absolute path
            # most of the time.
            # CORRECTION: but it doesn't work if no relative paths exists (e.g. different drives
            # or network paths) so then we revert to the absolute path.
            # I'm really not sure about this code.
            try:
                path = os.path.relpath(directory / fname, os.getcwd())
            except ValueError:
                path = os.path.abspath(directory / fname)

            if not os.path.exists(path):
                # well, we'll just try the basic path then. Dammit.
                path = directory / fname
                if not path.exists():
                        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

            def load(path: Path) -> Tuple[np.ndarray, float, float]:
                logger.debug(f"Loading {path} at bitdepth {bitdepth}, leftjustified={leftjustified}")
                if rawloader is not None and rawloader.is_raw_file(path):
                    return rawloader.load(path, bitdepth=bitdepth, leftjustified=leftjustified)
                else:
                    return load_rgb_image(path, bitdepth=bitdepth, leftjustified=leftjustified)

            if cache is None:
                img, dn_min, dn_max = load(path)
            else:
                date = os.path.getmtime(path)
                # if the file is in the cache and the date is the same, use the cached data
                if path in cache and cache[path][1] == date:
                    # use the cached data
                    img, dn_min, dn_max = cache[path][0], *cache[path][2]
                    ui.log(f"Using cached image for {path}")
                else:
                    # update the cache
                    ui.log(f"Loading image for {path} into cache")
                    img, dn_min, dn_max = load(path)
                    cache[path] = (img, date, (dn_min, dn_max))

            if dn_ranges is not None:
                dn_ranges[str(fname)] = (dn_min, dn_max)

            # convert to greyscale if required. But we don't use the
            # cvtColor function because it will use a more complex formula
            # that takes human perception into account. We want to keep the
            # original values, so we just take the mean of the three channels.
            if len(img.shape) == 3:
                img = np.mean(img, axis=2).astype(np.float32)

            # build source data for this image
            filtpos, searchtype = getFilterSearchParam(path)
            ext = StringExternal("Multi", os.path.abspath(path))
            if camera:
                filt = getFilter(camera, filtpos, searchtype)
                source = Source().setBand(filt).setInputIdx(inpidx).setExternal(ext)
            else:
                # sometimes we don't know what the camera is, so we can't get the filter.
                # This can happen in gencam.
                source = Source().setBand(f"{searchtype}={filtpos}").setInputIdx(inpidx).setExternal(ext)

            # img /= filt.transmission
            imgs.append(img)
            sources.append(source)

    # construct the imagecube
    if len(imgs) > 0:
        if len(set([x.shape for x in imgs])) != 1:
            raise Exception("all images must be the same size in a multifile")
        img = image.imgmerge(imgs).astype(np.float32)
        img = ImageCube(img, mapping, MultiBandSource(sources))
    else:
        img = None

    return Datum(Datum.IMG, img)


def pds4(inputlist: Union[ProductList, List[Union[DataProduct, str]]],
         multValue: Optional[float] = 1,
         mapping: Optional[ChannelMapping] = None,
         selection: Optional[List[int]] = None,
         inpidx: Optional[int] = None
         ) -> Datum:
    """Load a set of PDS4 data products from

    - a ProductList, or
    - a list of DataProducts from proctools, or
    - a list of strings which are the filenames of the PDS4 data product labels

    If they are all images, they will be combined into an image cube and returned as a Datum
    They must be the same size.

    Other data products are not yet supported, but it is envisioned that they will also be combined into
    a single Datum.

    Arguments:

        - inputlist: The list of data products to load (either a ProductList or a list of DataProducts)
        - multValue: The value to multiply the nominal and uncertainty data by (1 by default)
        - mapping: The mapping to use for the image cube (none by default - the cube will create one)
        - selection: Indices of items which should actually be used (all by default)
        - inpidx: The input index to use for the data products (none by default)
    """

    # NOTE:
    # This is the only load method which isn't used by the corresponding InputMethod. As such, it's
    # intended for use in scripts.

    # Determine the input type and convert it to a ProductList
    if isinstance(inputlist, list):
        if all([isinstance(x, DataProduct) for x in inputlist]):
            inputlist = ProductList(inputlist)
        elif all([isinstance(x, str) for x in inputlist]):
            plist = [DataProduct.from_file(x) for x in inputlist]
            inputlist = ProductList(plist)
        else:
            raise ValueError("All elements of the list must be DataProducts or strings")

    return inputlist.toDatum(multValue=multValue, mapping=mapping, selection=selection, inpidx=inpidx)


def parc(fname: str, itemname: str, inpidx: int = None) -> Optional[Datum]:
    """Load a Datum from a PCOT datum archive (PARC) file. We also patch the sources, overwriting the source data
    in the archive because we want the data to look like it came from the archive and not whatever
    the archive was created from. This may seem a bit rude - and that we're losing a record of something
    that might be important - but otherwise we could get bogged down with references to data on other systems.
    # Later we may revise this to avoid lossy source loading for (say) PDS4 products.

    - fname: the name of the archive file
    - itemname: the name of the item in the archive
    - inpidx: the input index to use or None if not connected to a graph input
    """

    try:
        return readParc(fname, itemname, inpidx)    # delegated to the datumstore module
    except FileNotFoundError as e:
        # we throw this to be consistent with the other methods
        raise Exception(f"Cannot read file {fname}") from e

