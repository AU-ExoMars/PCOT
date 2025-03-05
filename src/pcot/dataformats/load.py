import errno
import logging
import os
from typing import List, Tuple, Optional, Union, Dict, Any

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
from pcot.ui.presetmgr import PresetOwner
from pcot.utils import image
from pcot.utils.datumstore import readParc

logger = logging.getLogger(__name__)


def rgb(fname: str, inpidx: int = None, mapping: ChannelMapping = None) -> Datum:
    """Load an imagecube from an RGB file (png, jpeg etc.)

    - fname: the filename
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    """

    # might seem a bit wasteful having three of them, but seems more logical to me.
    e = StringExternal("RGB", fname)
    sources = MultiBandSource([
        Source().setBand("R").setExternal(e).setInputIdx(inpidx),
        Source().setBand("G").setExternal(e).setInputIdx(inpidx),
        Source().setBand("B").setExternal(e).setInputIdx(inpidx),
    ])

    img = ImageCube.load(fname, mapping, sources)  # this can throw an exception if the file is not found
    return Datum(Datum.IMG, img)


def envi(fname: str, inpidx: int = None, mapping: ChannelMapping = None) -> Datum:
    """Load an imagecube from an ENVI file

    - fname: the name of the .hdr (header) file - the .dat (data) file must be in the same directory
      and have the same name (except for the extension)
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    """

    from pcot.dataformats.envi import load

    h, img = load(fname)

    # construct the source data
    e = StringExternal("ENVI", f"ENVI:{fname}")
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


def multifile(directory: str,
              fnames: List[str],
              preset: Optional[str] = None,
              filterpat: str = None,
              bitdepth: int = None,
              camera: str = None,
              rawloader: Optional[RawLoader] = None,
              inpidx: int = None,
              mapping: ChannelMapping = None,
              cache: Dict[str, Tuple[np.ndarray, float]] = None) -> Datum:
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
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    - camera: the name of the camera to use for filter name lookup etc.
    - rawloader: a RawLoader object to use for loading raw files (unused if we're not loading raw files)
    - cache: a dictionary of cached data to avoid loading the same file multiple times.
      The key is the filename and the value is a tuple of the image data and the time it was loaded.

    The regular expression works thus:
        - If the filterpat contains ?P<lens> and ?P<n>, then lens+n is used to look up the filter by position.
          For example lens=L and n=01 would look up L01 in the filter position
        - Otherwise if the filterpat contains ?<name>, then name is used to look up the filter by name.
        - Otherwise if the filterpat contains ?<cwl>, then cwl is used to look up the filter's wavelength.
        - If these all fail, a "dummy" filter is used.

    an example:

        `.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*`

        - `.*` matches any characters
        - `(?P<lens>L|R)` matches L or R and assigns it to the lens group
        - `WAC` matches "WAC" (Wide Angle Camera)
        - `(?P<n>[0-9][0-9])` matches two digits and assigns them to the n group
        - `.*` matches any characters

        So for a filename like "Set18_LWAC01.png", the filter position would be "L01".

    """

    from pcot.inputs.multifile import presetModel
    logger.debug(f"Multifile load from directory {directory}")
    if rawloader is None:
        class RawPresets(PresetOwner):
            """
            This class stores presets for the multifile input method. It is used to hold settings
            for loading raw data. In normal multifile loading, the multifile widget is the preset owner
            (because it's the thing which has presets).
            """
            def __init__(self):
                # initialise with the settings passed into the containing function
                self.camera = camera
                self.filterpat = filterpat
                self.bitdepth = bitdepth
                self.rawloader = rawloader

            def applyPreset(self, d: Dict[str, Any]):
                # override the values with the ones from the preset file, but
                # only if they haven't been set already
                self.camera = self.camera or d['camera']
                self.filterpat = self.filterpat or d['filterpat']
                self.bitdepth = self.bitdepth or (None if d is None else d.get('bitdepth', None))
                if self.rawloader is None:
                    self.rawloader = RawLoader()
                    self.rawloader.deserialise(d['rawloader'])

        # create the reader object, which will initialise its values with those
        # passed into the function and then fill missing values with those from the preset.
        # This is a slight abuse of the normal system seen in the multifile input method, where
        # the multifile input widget is a PresetOwner (i.e. a thing which has presets).
        r = RawPresets()
        if preset is not None:
            r.applyPreset(presetModel.loadPresetByName(r, preset))
        # now we can use the settings in r
        filterpat = r.filterpat or r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        camera = r.camera or pcot.config.default_camera
        rawloader = r.rawloader
        
    def getFilterSearchParam(p) -> Tuple[Optional[Union[str, int]], Optional[str]]:
        """Returns the thing to search for to match a filter to a path and the type of the search"""
        if filterre is None:
            return None, None
        else:
            m = filterre.match(p)
            if m is None:
                logger.critical(f"NO MATCH FOUND FOR path {p}, regex {filterre}")
                return None, None
        
            m = m.groupdict()
            if '<lens>' in filterpat:
                if '<n>' not in filterpat:
                    raise Exception(f"A filter with <lens> must also have <n>")
                # lens is either left or right
                lens = m.get('lens', '')
                n = m.get('n', '')
                return lens + n, 'pos'
            elif '<name>' in filterpat:
                return m.get('name', ''), 'name'
            elif '<cwl>' in filterpat:
                return int(m.get('cwl', '0')), 'cwl'
            else:
                return None, None

    # first compile the regex
    import re
    try:
        filterre = re.compile(filterpat)
    except re.error as e:
        logger.error(f"Error in filter pattern: {e}")
        filterre = None

    sources = []  # array of source sets for each image
    imgs = []  # array of actual images (greyscale, numpy)

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
                path = os.path.relpath(os.path.join(directory, fname), os.getcwd())
            except ValueError:
                path = os.path.abspath(os.path.join(directory, fname))

            if not os.path.exists(path):
                # well, we'll just try the basic path then. Dammit.
                path = os.path.join(directory, fname)
                if not os.path.exists(path):
                        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

            def load(path: str) -> np.ndarray:
                if rawloader is not None and rawloader.is_raw_file(path):
                    return rawloader.load(path, bitdepth=bitdepth)
                else:
                    return load_rgb_image(path, bitdepth=bitdepth)

            if cache is None:
                img = load(path)
            else:
                date = os.path.getmtime(path)
                # if the file is in the cache and the date is the same, use the cached data
                if path in cache and cache[path][1] == date:
                    # use the cached data
                    img = cache[path][0]
                    ui.log(f"Using cached image for {path}")
                else:
                    # update the cache
                    ui.log(f"Loading image for {path} into cache")
                    img = load(path)
                    cache[path] = (img, date)

            # convert to greyscale if required. But we don't use the
            # cvtColor function because it will use a more complex formula
            # that takes human perception into account. We want to keep the
            # original values, so we just take the mean of the three channels.
            if len(img.shape) == 3:
                img = np.mean(img, axis=2).astype(np.float32)

            # build source data for this image
            filtpos, searchtype = getFilterSearchParam(path)
            filt = getFilter(camera, filtpos, searchtype)
            # img /= filt.transmission

            ext = StringExternal("Multi", os.path.abspath(path))
            source = Source().setBand(filt).setInputIdx(inpidx).setExternal(ext)

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

