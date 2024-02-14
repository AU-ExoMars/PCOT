import errno
import os
from typing import List, Tuple, Optional, Union, Dict

import numpy as np
import logging
from dateutil import parser
from proctools.products import DataProduct

from pcot import ui
from pcot.dataformats.pds4 import PDS4Product, PDS4ImageProduct
from pcot.datum import Datum
from pcot.filters import getFilter, Filter
from pcot.imagecube import ChannelMapping, ImageCube, load_rgb_image
from pcot.sources import StringExternal, MultiBandSource, Source

from pcot.utils import image

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


def multifile(directory: str, fnames: List[str],
              filterpat: str = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*',
              mult: np.float32 = 1.0,
              inpidx: int = None, mapping: ChannelMapping = None,
              filterset: str = 'PANCAM',
              cache: Dict[str, Tuple[np.ndarray, float]] = None) -> Datum:
    """Load an imagecube from multiple files (e.g. a directory of .png files),
    where each file is a monochrome image of a different band. The names of
    the filters for each band are derived from the filenames using the filterpat
    regular expression pattern. The filter set specifies which table is used
    to look up the filter names.

    - directory: the directory containing the files
    - fnames: the list of filenames
    - filterpat: a regular expression pattern that extracts the filter name from the filename
    - mult: a multiplier to apply to the image data (which is often a very low intensity)
    - inpidx: the input index to use or None if not connected to a graph input
    - mapping: the channel mapping to use or None if the default
    - filterset: the name of the filter set to use for filter name lookup
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

    def getFilterSearchParam(p) -> Tuple[Optional[Union[str, int]], Optional[str]]:
        """Returns the thing to search for to match a filter to a path and the type of the search"""
        if filterre is None:
            return None, None
        else:
            m = filterre.match(p)
            if m is None:
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
            try:
                path = os.path.relpath(os.path.join(directory, fname), os.getcwd())
            except ValueError:
                path = os.path.abspath(os.path.join(directory, fname))

            if not os.path.exists(path):
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

            if cache is None:
                img = load_rgb_image(path)
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
                    img = load_rgb_image(path)
                    cache[path] = (img, date)

            # convert to greyscale if required. But we don't use the
            # cvtColor function because it will use a more complex formula
            # that takes human perception into account. We want to keep the
            # original values, so we just take the mean of the three channels.
            if len(img.shape) == 3:
                img = np.mean(img, axis=2).astype(np.float)

            # build source data for this image
            filtpos, searchtype = getFilterSearchParam(path)
            filt = getFilter(filterset, filtpos, searchtype)
            ext = StringExternal("Multi", os.path.abspath(path))
            source = Source().setBand(filt).setInputIdx(inpidx).setExternal(ext)

            imgs.append(img)
            sources.append(source)

    # construct the imagecube
    if len(imgs) > 0:
        if len(set([x.shape for x in imgs])) != 1:
            raise Exception("all images must be the same size in a multifile")
        img = image.imgmerge(imgs).astype(np.float32)
        img = ImageCube(img * mult, mapping, MultiBandSource(sources))
    else:
        img = None

    return Datum(Datum.IMG, img)


def pds4(inputlist: List[DataProduct]):
    """Load a set of PDS4 data products. If they are all images, they will be combined into an image cube.
    They must be the same size. Other data products are not yet supported."""

    products: List[PDS4Product] = []

    tp = None       # type of the objects found so far.
    for dat in inputlist:
        if type is None:
            tp = dat.meta.type
        elif tp != dat.meta.type:
            raise Exception("All PDS4 data products must be of the same type")

    # this stuff needs to be extracted into a factory function.

    for dat in inputlist:
        m = dat.meta
        start = parser.isoparse(m.start)

        logger.debug(f"Creating new product {m.lid}")
        # only generate a new product object if we don't have it already
        cwl = int(m.filter_cwl)
        fwhm = int(m.filter_bw)
        id = m.filter_id
        sol = int(m.sol_id)
        seq = int(m.seq_num)
        ptu = float(m.rmc_ptu)
        # use the index for the given sol, adding one to it.

        # show_meta(m)

        # construct a filter from that data
        filt = Filter(cwl, fwhm, transmission=1.0, name=id, position=id)

        # we fudge up the index after this loop, post sort.
        prod = PDS4ImageProduct(m.lid, 0, start, sol, seq, filt, m.camera, ptu)
        products.append(prod)

    # we sort by camera, then freq, then bandwidth, then start
    products.sort(key=lambda p: (p.camera, p.filt.cwl, p.filt.fwhm, p.start))

    # products with the same sol should have different indices
    # for positioning
    solcounts = {}
    for p in products:
        idx = solcounts.get(p.sol_id, 0) + 1
        solcounts[p.sol_id] = idx
        p.idx = idx

    # TODO convert to imagecube