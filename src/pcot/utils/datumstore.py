import dataclasses
import sys
import time
from typing import Dict, Optional, Tuple

from pcot.datum import Datum
from pcot.document import Document
from pcot.utils.archive import Archive, FileArchive
from pcot.sources import StringExternal, SourceSet, MultiBandSource, Source


class DatumStore:
    """
    This class allows Datum objects to be stored into, and retrieved from, an Archive object.
    It's mainly used for handling blocks of data used in calibration pipeline and pipeline emulation - flatfields
    and the like.

    It's not used for serialisation, however, because serialisation is primarily for storing XForms and graph data.
    However, it can be used for saving Datum objects to a file in a simple way - for example, the ".parc" data
    format is an archive containing one item, called "main".

    This uses a LRU-cache of a slightly unusual kind, in that the size is specified in bytes. If reading
    a new item would exceed this size, least-recently-used items of non-zero size are removed until there
    is enough space. This is because Datum objects can be quite large, and we don't want to run out of memory.

    Usage example for writing:
        with FileArchive("foo.zip", "w") as a, DatumStore(a) as da:
            da.writeDatum("bar", some_datum_object)
            da.writeDatum("baz", some_other_datum_object)

    Which is sort-of the same as:

        with FileArchive("foo.zip", "w") as a:
            with DatumStore(a) as da:
                da.writeDatum("bar", some_datum_object)
                da.writeDatum("baz", some_other_datum_object)

    or you can do:

        with FileArchive("foo.zip", "w") as a:
            da = DatumStore(a)
            da.writeDatum("bar", some_datum_object)
            da.writeDatum("baz", some_other_datum_object)
            da.writeManifest()

    This is because we have to write the manifest at the end. The context manager will check we have the archive
    open in write mode, and will write the manifest automatically. If we're not using a CM we have to do it ourselves.

    Usage example for reading:
            a = DatumStore(FileArchive(fn), 1000)
            d = a.get("test", None)

    The Zip archive is only open while data is being written or read (PCOT archive objects - which this class uses -
    are context managers).

    Be VERY SURE that you don't keep any references to the Datum objects, or the LRU deletion won't work!
    """

    @dataclasses.dataclass
    class CachedItem:
        """
        This is a simple class to hold the information we need to cache an item in the DatumArchive.
        """
        size: int  # size in bytes
        time: float  # timestamp when accessed
        datum: Datum  # the Datum object

    archive: Archive
    cache: Dict[str, CachedItem]
    max_size: int
    write_mode: bool

    # this is a manifest of the items in the archive.
    # It's a dictionary of name: (datumtype name, description, repr).
    # Description is an optional string provided when the item is written, repr is the string
    # representation of the datum.
    manifest: Dict[str, Tuple[str, str, str]] = {}

    def __init__(self, archive: Archive, max_size: int = sys.maxsize):
        """
        Create a new DatumArchive object. The size parameter is the maximum total size of the cached items
        in bytes.
        """

        self.archive = archive
        self.cache = {}
        self.size = max_size
        self.read_count = 0

        if not self.archive.is_open():
            # assume we are reading. Read the manifest.
            with self.archive as a:
                if (m := a.readJson("MANIFEST")) is not None:
                    self.manifest = m
        else:
            self.manifest = {}
            self.write_mode = True

    def __enter__(self):
        """This will just return self; the magic happens in __exit__"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """If we're in write mode, write the manifest."""
        self.writeManifest()

    def writeManifest(self):
        """Write the manifest to the archive. This is only done in write mode."""
        if self.archive.mode == 'w':
            self.archive.writeJson("MANIFEST", self.manifest)

    def writeDatum(self, name: str, d: Datum, description: str = ""):
        """This is used to write a Datum object to the archive; it's doesn't write to the cache. It will
        probably only be used in scripts that prepare archives.

        description: an optional text description of the datum

        This MUST BE inside a context manager because the archive must be open for all items.
        """

        if not self.archive.is_open():
            raise Exception("archive must be open to write")

        # update the manifest
        self.manifest[name] = (d.tp.name, description, str(d.val))

        # write the item to the archive
        self.archive.writeJson(name, d.serialise())

    def total_size(self):
        return sum([item.size for item in self.cache.values()])

    def get(self, name, doc: Optional[Document]) -> Optional[Datum]:
        """
        Get an item from the archive. If it's already in the cache, return it from there. Otherwise, read it from
        the archive and return it. If it's not in the archive, return None. We need the document so that the
        sources can be reconstructed for images.

        This MUST NOT be inside an Archive context manager; it will open/close the archive with a context
        manager itself.
        """

        # Note that we don't bother to check the manifest.

        if self.archive.is_open():
            raise Exception("archive must not be 'pre-opened' to read")

        if name not in self.cache:
            # read the item first - we need to know how big it is.
            with self.archive as a:
                if (item := a.readJson(name)) is None:
                    return None
                # and deserialise it
                datum = Datum.deserialise(item, doc)
                size = datum.getSize()
                # we may need to make room in the cache. Total the size to find out.
                while self.total_size() + size > self.size:
                    # find the least-recently-used item with non-zero size
                    found = None
                    oldest = time.perf_counter()
                    for k, v in self.cache.items():
                        if v.size > 0 and v.time < oldest:
                            oldest = v.time
                            found = k
                    if found is not None:
                        del self.cache[found]  # delete it. This may not work if we have stale references!!!
                    else:
                        raise Exception("internal error: cache must be lying about size or cache is too small")

                # construct a CachedItem - it's OK for the time to be zero here, it will be overwritten very
                # soon so there's no point calling time().
                self.cache[name] = DatumStore.CachedItem(datum.getSize(), 0, datum)
                self.read_count += 1

        self.cache[name].time = time.perf_counter()  # set timestamp of access
        return self.cache[name].datum  # and return


def writeParc(filename: str, d: Datum, description=None):
    """Write a PARC file - a DatumStore with a single item called "main".

    """
    with FileArchive(filename, "w") as a, DatumStore(a) as da:
        da.writeDatum("main", d, description=description)
        da.writeManifest()


def readParc(fname: str, itemname: str, inpidx: int = None) -> Optional[Datum]:
    """Load a Datum from a Datum archive file. We also patch the sources, overwriting the source data
    in the archive because we want the data to look like it came from the archive and not whatever
    the archive was created from. This may seem a bit rude - and that we're losing a record of something
    that might be important - but otherwise we could get bogged down with references to data on other systems.
    # Later we may revise this to avoid lossy source loading for (say) PDS4 products.

    - fname: the name of the archive file
    - itemname: the name of the item in the archive
    - inpidx: the input index to use or None if not connected to a graph input
    """


    if fname is not None and itemname is not None:
        fa = FileArchive(fname)
        ds = DatumStore(fa)
        datum = ds.get(itemname, None)
    else:
        return None

    if datum is None:
        return None

    # Patch sources as described above

    e = StringExternal("PARC", f"{fname}:{itemname}")  # the label we'll attach

    def patchSource(s):
        if isinstance(s, SourceSet):
            # take all the sources in a sources set and patch them. Then merge any duplicates.
            return SourceSet(set([patchSource(ss) for ss in s]))
        elif isinstance(s, MultiBandSource):
            # perform the patch operation on all bands in a MultiBandSource
            return MultiBandSource([patchSource(ss) for ss in s])
        elif isinstance(s, Source):
            # for each root source, we create a new source with our new external (giving the name of the archive)
            # and the input index. Keep the band data (which will be a filter or a band name).
            return Source().setExternal(e).setBand(s.band).setInputIdx(inpidx)

    datum.val.sources = patchSource(datum.val.sources)

    #
    # if isinstance(datum.val.sources, MultiBandSource):
    #     sources = []
    #     # for each band, we make a new source with the same bands and the same external
    #     for s in datum.val.sources:
    #         # get the original sources; there may be more than one for each band
    #         ss = s.getSources()
    #         # flatten them down into a single set of bands
    #         bands = set([s.band for s in ss])
    #         # create sources from those bands
    #         ss = SourceSet([Source().setBand(b).setExternal(e).setInputIdx(inpidx) for b in bands])
    #         sources.append(ss)
    #     ms = MultiBandSource(sources)
    #     datum.val.sources = ms

    return datum

