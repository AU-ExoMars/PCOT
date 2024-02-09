import pcot
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.sources import StringExternal, MultiBandSource, Source


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
