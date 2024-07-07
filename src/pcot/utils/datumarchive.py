import dataclasses
import time
from typing import Dict, Optional

from pcot.datum import Datum
from pcot.document import Document
from pcot.utils.archive import Archive


@dataclasses.dataclass
class CachedItem:
    """
    This is a simple class to hold the information we need to cache an item in the DatumArchive.
    """
    size: int  # size in bytes
    time: float  # timestamp when accessed
    datum: Datum  # the Datum object


class DatumArchive:
    """
    This class allows Datum objects to be stored into, and retrieved from, an Archive object. It's not used
    for serialisation, however, because serialisation is primarily for storing XForms and graph data.

    This uses a LRU-cache of a slightly unusual kind, in that the size is specified in bytes. If reading
    a new item would exceed this size, least-recently-used items of non-zero size are removed until there
    is enough space. This is because Datum objects can be quite large, and we don't want to run out of memory.

    The Zip archive is only open while data is being written or read (PCOT archive objects are context managers).

    Be VERY SURE that you don't keep any references to the Datum objects, or the LRU deletion won't work!
    """

    archive: Archive
    cache: Dict[str, CachedItem]
    max_size: int

    def __init__(self, archive: Archive, max_size: int):
        """
        Create a new DatumArchive object. The size parameter is the maximum total size of the cached items
        in bytes.
        """

        self.archive = archive
        self.cache = {}
        self.size = max_size

    def writeDatum(self, name: str, d: Datum):
        """This is used to write a Datum object to the archive; it's doesn't write to the cache. It will
        probably only be used in scripts that prepare archives."""
        with self.archive as a:
            a.writeJson(name, d.serialise())

    def get(self, name, doc: Document) -> Optional[Datum]:
        """
        Get an item from the archive. If it's already in the cache, return it from there. Otherwise, read it from
        the archive and return it. If it's not in the archive, return None. We need the document so that the
        sources can be reconstructed for images.
        """

        if name not in self.cache:
            # we may need to make room in the cache. Total the size to find out.
            while sum([item.size for item in self.cache.values()]) > self.size:
                # find the least-recently-used item with non-zero size
                found = None
                oldest = time.time()
                for k, v in self.cache.items():
                    if v.size > 0 and v.time < oldest:
                        oldest = v.time
                        found = k
                if found is not None:
                    del self.cache[found]  # delete it. This may not work if we have stale references!!!
                else:
                    raise Exception("internal error: cache must be lying about size")

            # now we can read in an item
            with self.archive as a:
                if (item := a.readJson(name)) is None:
                    return None
                # and deserialise it
                datum = Datum.deserialise(item, doc)
                # construct a CachedItem - it's OK for the time to be zero here, it will be overwritten very
                # soon so there's no point calling time().
                self.cache[name] = CachedItem(datum.getSize(), 0, datum)

        self.cache[name].time = time.time()  # set timestamp of access
        return self.cache[name].datum  # and return
