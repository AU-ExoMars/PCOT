import dataclasses
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from pcot.datum import Datum
from pcot.document import Document
from pcot.utils.archive import Archive, FileArchive
from pcot.sources import StringExternal, SourceSet, MultiBandSource, Source


@dataclasses.dataclass
class Metadata:
    """An item in the manifest. The name is not included, because this is always part of a dict
    of name -> manifest item."""
    datumtype: str  # the type of the datum (as a string)
    description: str  # a description of the datum - could be empty
    repr: str  # the string representation of the datum
    created: datetime  # the time when created in ISO 8601 format

    def serialise(self):
        return {
            "datumtype": self.datumtype,
            "description": self.description,
            "repr": self.repr,
            "created": self.created.isoformat()
        }

    @staticmethod
    def deserialise(d):
        return Metadata(
            d["datumtype"],
            d["description"],
            d["repr"],
            datetime.fromisoformat(d["created"])
        )


class DatumStore:
    """
    This class allows Datum objects to be stored into, and retrieved from, an Archive object. It is used to
    implement the PARC file format, which handles archives of Datum objects.

    Its simplest use is to store a single Datum object in an archive, but it can also be used to store multiple
    datum objects which it can handle in an LRU cache. This mode is used for handling collections of data used in
    calibration pipeline and pipeline emulation - flatfields and the like.

    This uses a LRU-cache of a slightly unusual kind, in that the size is specified in bytes. If reading
    a new item would exceed this size, least-recently-used items of non-zero size are removed until there
    is enough space. This is because Datum objects can be quite large, and we don't want to run out of memory.

    By default the cache is infinitely large, so objects will sit around until the store goes away!!!

    Usage example for writing:
            with FileArchive("foo.parc", "w") as a:
                da = DatumStore(a)
                da.writeDatum("bar", some_datum_object)
                da.writeDatum("baz", some_other_datum_object)

    Usage example for reading:
            a = DatumStore(FileArchive(fn), 1000)
            d = a.get("test", None)

    Note the difference - when writing, the archive is open for writing either using open() or inside a context manager.

    The Zip archive is only open while data is being written or read (PCOT archive objects - which this class uses -
    are context managers).

    Be VERY SURE that you don't keep any references to the Datum objects, or the LRU deletion won't work!
    
    Internal format: each item is a JSON file. Strings in that JSON which are of the form "ARAE-n" are actually
    numpy arrays stored in files of that name. This is handled by FileArchive.

    Each JSON file also has a metadata file with the same name but with a .meta extension. This is a JSON file
    containing a serialisation of a Metadata object. These are stored in the manifest dictionary.
    
    
    """

    @dataclasses.dataclass
    class CachedItem:
        """
        This is a simple class to hold the information we need to cache an item in the archive.
        """
        size: int  # size in bytes
        time: float  # timestamp when accessed
        datum: Datum  # the Datum object

    archive: Archive
    cache: Dict[str, CachedItem]
    max_size: int
    write_mode: bool

    # this is a manifest of the items in the archive.
    # It's a dictionary of name -> Metadata
    manifest: Dict[str, Metadata]

    def __init__(self, archive: Archive, max_size: int = sys.maxsize):
        """
        Create a new DatumStore object. The size parameter is the maximum total size of the cached items
        in bytes.
        """

        self.archive = archive
        self.cache = {}
        self.manifest = {}
        self.size = max_size
        self.read_count = 0

        if not self.archive.is_open():
            # assume we are reading. When reading, we create the archive outside a context manager which
            # means enter hasn't been called so the ZipFile object hasn't been created.
            with self.archive as a:   # This briefly opens the archive to read the manifest
                self.readManifest(a)
        else:
            if not self.archive.is_writable():
                raise Exception("archive must be open for writing if it is open when passed to a DatumStore constructor (don't use a context manager for the archive in read mode)")
            self.manifest = {}
            self.write_mode = True
            
    def close(self):
        self.archive.close()

    def readManifest(self, archive):
        names = archive.getNames()
        for x in names:
            # every item in the archive that ends with .meta should be a metadata file for a file without
            # that extension.
            if x.endswith(".meta"):
                # for every .meta file we get the name of the file it's associated with
                name = x[:-5]
                if name in names:
                    # and if it exists in the archive we load the metadata file.
                    try:
                        if (d := archive.readJson(x)) is not None:
                            self.manifest[name] = Metadata.deserialise(d)
                        else:
                            raise Exception(f"metadata missing")
                    except Exception as e:
                        print(f"Error reading metadata for {name}: {e}")

    def writeManifest(self):
        """Write the manifest to the archive. This is only done in write mode."""
        if self.archive.is_writable():
            # serialise the manifest
            m = {k: v.serialise() for k, v in self.manifest.items()}
            # we may be appending, so we need to permit replacement of the manifest
            self.archive.writeJson("MANIFEST", m, permit_replace=True)

    def writeDatum(self, name: str, d: Datum, description: str = ""):
        """This is used to write a Datum object to the archive; it doesn't write to the cache. It will
        probably only be used in scripts that prepare archives.

        description: an optional text description of the datum
        """

        if not self.archive.is_open() or not self.archive.is_writable():
            raise Exception("archive must be open to write")

        # in most circumstances this is a double check, another check having been done up-stack
        if name is None:
            raise Exception("name must not be None in writeDatum")

        # update the manifest
        meta = Metadata(d.tp.name, description, str(d), datetime.now())
        self.manifest[name] = meta

        # write the item to the archive
        self.archive.writeJson(name, d.serialise())
        # and the metadata too
        self.archive.writeJson(name+".meta", meta.serialise())

    def total_size(self):
        return sum([item.size for item in self.cache.values()])

    def getMetadata(self, name: str) -> Metadata:
        """Get the metadata item for a given name, or None if it doesn't exist."""
        return self.manifest.get(name, None)

    def getManifest(self) -> Dict[str, Metadata]:
        """Get the entire menifest of metadata objects"""
        return self.manifest

    def get(self, name) -> Optional[Datum]:
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
                datum = Datum.deserialise(item)
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

    def clearCache(self):
        """Clear the cache of all items. This is useful if you want to free up memory."""
        self.cache = {}


def readParc(fname: str, itemname: str = 'main', inpidx: int = None) -> Optional[Datum]:
    """Load a Datum from a Datum archive file. We also patch the sources, overwriting the source data
    in the archive because we want the data to look like it came from the archive and not whatever
    the archive was created from. This may seem a bit rude - and that we're losing a record of something
    that might be important - but otherwise we could get bogged down with references to data on other systems.
    # Later we may revise this to avoid lossy source loading for (say) PDS4 products.

    - fname: the name of the archive file
    - itemname: the name of the item in the archive ('main' by default)
    - inpidx: the input index to use or None if not connected to a graph input
    """

    if fname is not None and itemname is not None:
        fa = FileArchive(fname)
        ds = DatumStore(fa)
        datum = ds.get(itemname)
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
