import dataclasses
import sys
import time
from typing import Dict, Optional, Tuple

from pcot.datum import Datum
from pcot.document import Document
from pcot.utils.archive import Archive, FileArchive


class DatumStore:
    """
    This class allows Datum objects to be stored into, and retrieved from, an Archive object.
    It's mainly used for handling blocks of data used in calibration pipeline and pipeline emulation - flatfields
    and the like.

    It's not used for serialisation, however, because serialisation is primarily for storing XForms and graph data.

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
