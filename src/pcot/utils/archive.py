import json
import datetime
import dataclasses
import getpass
from pathlib import Path
from typing import Callable, Union
from dataclasses import dataclass
from enum import Enum

import numpy as np
import zipfile
from io import BytesIO

import logging
logger = logging.getLogger(__name__)

class ArchiveType(Enum):
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown (no metadata)"
    DOCUMENT = "PCOT document"
    CAMERADATA = "camera data"
    IMAGECUBE = "imagecube"
    REFLDATA = "reflectance data"
    
    def __str__(self):
        return self.value
        

def _getpcotversion():
    # ugly hack to deal with circular import
    import pcot
    return pcot.__fullversion__
    
def _getdate():
    return datetime.datetime.now().isoformat()


@dataclasses.dataclass
class Metadata:
    """
    Objects of this class hold common data to all PCOT archives.
    
    * metadata is created when the archive is initialised. Initially the date is unset.
    * When the file is opened, any metadata is read, overwriting that initial
      metadata (so the date will become set)
    * The metadata is updated when the archive is written, adding date/author etc.
    * We can check in `lsparc`etc. whether the file has metadata by checking that date field;
      this is done with `is_loaded`.
    """
    type: ArchiveType = ArchiveType.UNSPECIFIED
    
    author: str = dataclasses.field(default_factory=getpass.getuser)

    # written date in ISO format, or None if the metadata is "fresh" - not yet
    # written to an archive. We use this to check whether we need to save this
    # data to history when we write, and also to check whether there is "real"
    # metadata in an archive.
    date: str = None
    
    # ugly hack for circular import
    pcotversion: str = dataclasses.field(default_factory=_getpcotversion)

    # this is a list of some items (notably not type)
    history: list[dict] = dataclasses.field(default_factory=list)
    
    def is_loaded(self):
        """If the metadata is "fresh" data that's not yet written to an archive,
        the date will not be set"""
        return self.date is not None
    
    def serialise(self):
        """Convert to a serialisable dict - note the type, though: we'll need to use
        our serialisers to work with this."""
        return dataclasses.asdict(self)
        
    @staticmethod
    def deserialise(d):
        """Create a metadata item from a dict; again this needs to have gone through
        our deserialiser hook to make sure the ArchiveType is correct"""
        return Metadata(**d)
        
    def save_history(self):
        """adds some of the metadata's current data to the history list of dicts"""
        new_row = {k:getattr(self,k) for k in ['author','date','pcotversion']}
        self.history.insert(0,new_row)
        
    def update(self):
        """Update some fields in the metadata for saving"""
        import getpass
        self.author = getpass.getuser()
        self.date = _getdate()
        self.pcotversion = _getpcotversion()


# Basic serialisers/deserialisers. Numpy arrays are handled differently,
# see the docstring for Archive.

serialisers={}  # dict of name to (serialiser,deserialiser) lambdas


def registerJsonSerialiser(name,ser,deser):
    """Call this with a class/type name, serialiser and deserialiser.
    Serialiser should take the object and turn it into JSON serialisable data
    Deserialiser should take that data and turn it back into the object."""
    serialisers[name]=(ser,deser)
    
def deserialiser(o):
    """This is the 'object_hook' for the json.loads - it turns dicts (JSON objects) with the key '_type' 
    into the original data."""
    if '_type' in o:
        tp = o['_type']
        if tp in serialisers:
            return serialisers[tp][1](o['val'])
        raise TypeError(f"Unknown JSON serialisation: {tp}")
    return o


def serialiser(o):
    """This is the 'default' for the json.dumps - it turns unserialisable types into JSON"""
    tp = o.__class__.__name__
    if tp in serialisers:
        return {'_type': tp, 'val':serialisers[tp][0](o)}
    raise TypeError


# register specific serialisers here.

registerJsonSerialiser("ArchiveType",
    lambda x: x.value,              # archive types are stored as their strings
    lambda x: ArchiveType(x)        # and when we deserialise, are turned back into ArchiveType
)


class Archive:
    """
    This class provides the ability to store multiple JSON files inside a single ZIP archive, which can also
    store numpy arrays, which can be indexed from the files. That sounds a bit complex. Here's an example:
    Imagine we have a dictionary like this:
    d  = { "foo": 1, "bar": 2, "baz" : <numpy array>, "boz": [<numpy array>, <numpy array>...] }
    So a dictionary containing a complex structure of lists, primitive types... and numpy arrays.
    We can't JSONify this normally, but with this class we can save it thus:
        with FileArchive("foo.zip", 'w') as a:
            a.writeJson("mydata",d)
    The structure will first be parsed, and all numpy arrays saved to the archive separately and replaced
    in the structure by strings of the form "ARAE-n" ("arae" is the Welsh for "array"). These strings are
    the names of the array files in the archive. The structure will now be converted to JSON (possible since
    all the arrays are now gone) and saved to the archive as "mydata."

    The data can be loaded back with:

        with FileArchive("foo.zip",'r') as a:
            d = a.readJson("mydata")

    and all the array tags will be replaced with the actual numpy arrays, read from the archive.

    The system can also be used to save to archives in memory by using "MemoryArchive" objects:

        # serialise to memory
        with MemoryArchive() as a:
            a.writeJson("fronk", xx)
            data = a.get()

        # and deserialize
        with MemoryArchive(data) as a:
            xx = a.readJson("fronk")
            print(xx)

    This is useful for serialisation/deserialisation in cut/paste operations.
    """

    def __init__(self, mode='r', progressCallback=None):
        self.mode = mode
        self.arrayct = 0
        self.zip = None
        self.progressCallback = progressCallback
        self.path = "(memory?)"
        # no metadata to start with - when we open, one will either be created or loaded if this
        # is a FileArchive - otherwise there may never be one.
        self.metadata = None

    def open(self):
        """Must open the zip, setting self.zip to the zipfile.ZipFile object"""
        pass

    def close(self):
        """Must close the zip file and set self.zip to None"""
        pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_writable(self):
        return self.mode in ['w', 'a']

    def is_open(self):
        return self.zip is not None

    def assert_read(self):
        if self.mode == 'w' or (self.mode == 'a' and self.metadata is not None):
            # we can read from an appending file ONLY IF it's that
            # first metadata read
            raise Exception("Archive is not open for reading")

    def assert_write(self):
        if not self.is_writable():
            raise Exception("Archive is not open for writing")

    def assert_unique_name(self, name):
        if name in self.zip.namelist():
            raise Exception(f"Name {name} is already in the archive")

    def progress(self, s):
        if self.progressCallback:
            self.progressCallback(s)

    def writeArray(self, name: str, a: np.ndarray):
        if self.zip is None:
            raise Exception("Archive is not open")
        self.assert_write()
        b = BytesIO()
        np.save(b, a)
        self.assert_unique_name(name)
        self.zip.writestr(name, b.getvalue())

    def writeArrayAndGenerateName(self, a: np.ndarray):
        logger.debug(f"Writing array to archive {str(self)}, size {a.shape}")
        name = "ARAE-{}".format(self.arrayct)
        self.writeArray(name, a)
        self.arrayct += 1
        logger.debug("Write done")
        return name

    def writeStr(self, name: str, string: str, permit_replace=False):
        if self.zip is None:
            raise Exception("Archive is not open")
        self.assert_write()
        logger.debug(f"Writing to {name} in {str(self)}")
        if not permit_replace:
            self.assert_unique_name(name)
        # I'm aware it'll do the encoding anyway, but I wanted to make it explicit
        self.zip.writestr(name, string.encode('utf-8'))

    def readArray(self, name: str) -> np.ndarray:
        if self.zip is None:
            raise Exception("Archive is not open")
        self.assert_read()
        b = self.zip.read(name)
        bio = BytesIO(b)
        a = np.load(bio)
        return a

    def readStr(self, name: str) -> str:
        if self.zip is None:
            raise Exception("Archive is not open")
        self.assert_read()
        b = self.zip.read(name)
        return b.decode('utf-8')

    # will take a nested structure of lists and dicts to any depth, consisting of primitive types -
    # the sort of thing that can be turned into JSON. But it will also accept numpy arrays, which it
    # will save to the archive given and replace with string tags.

    def convertArraysToTags(self, d):
        if isinstance(d, list):
            return [self.convertArraysToTags(x) for x in d]
        elif isinstance(d, dict):
            return {k: self.convertArraysToTags(v) for k, v in d.items()}
        elif isinstance(d, tuple):
            return tuple([self.convertArraysToTags(x) for x in d])
        elif isinstance(d, np.ndarray):
            return self.writeArrayAndGenerateName(d)
        else:
            return d

    # does the inverse of the above, turning the string tags back into their numpy arrays from the archive

    def convertTagsToArrays(self, d):
        if isinstance(d, list):
            return [self.convertTagsToArrays(x) for x in d]
        elif isinstance(d, dict):
            return {k: self.convertTagsToArrays(v) for k, v in d.items()}
        elif isinstance(d, tuple):
            return tuple([self.convertTagsToArrays(x) for x in d])
        elif isinstance(d, str) and d.startswith("ARAE-"):
            self.progress(f"Extracting data array {d} from archive...")
            return self.readArray(d)
        else:
            return d

    def writeJson(self, name, d, permit_replace=False):
        """Write a JSON-serisalisable object. If permit_replace is true, we can replace
        an item with the same name. Otherwise we'll get an exception. This will be raised
        before the converted arrays get written.
        """
        if self.zip is None:
            raise Exception("Archive is not open")
        if not permit_replace:
            # do this BEFORE we convert the arrays to tags. It gets done in writeStr too!
            self.assert_unique_name(name)
        d = self.convertArraysToTags(d)
        s = json.dumps(d, sort_keys=True, indent=4, default=serialiser)
        self.writeStr(name, s, permit_replace=permit_replace)

    def readJson(self, name):
        if self.zip is None:
            raise Exception("Archive is not open")
        logger.debug(f"Reading {name} from {str(self)}")
        s = self.readStr(name)
        d = json.loads(s, object_hook=deserialiser)
        d = self.convertTagsToArrays(d)
        return d

    def getNames(self):
        return self.zip.namelist()


class FileArchive(Archive):
    """
    Used for ZIP files on disk.
    """

    def __init__(self, path: Union[Path,str], mode='r', progressCallback: Callable[[str], None] = None,
            metadata:Metadata=None,                     # if supplied, type will not be used
            type:ArchiveType=ArchiveType.UNSPECIFIED     # ignored if metadata is supplied (is used to build a metadata)
        ):

        """Open a Zip archive on disk.
        The mode is 'r' for read, 'w' for write, and 'a' for append.
        If "type" is set, add the type of the archive to the metadata for writing.
        This is just a string; some are defined in ArchiveTypes. The default is "unspecified".
        Metadata is only written when the archive is opened in write mode.
        """
        assert mode in ['r', 'w', 'a']
        super().__init__(mode, progressCallback=progressCallback)
        path = path if isinstance(path, Path) else Path(path)  # sometimes they are strings
        self.path = path

        # either create a new metadata item, or use the one passed in. 
        if metadata is None:
            self.metadata = Metadata(type=type)
        else:
            self.metadata = metadata

        # we haven't actually loaded metadata, this is a new archive. This could
        # change below. We use this to suppress adding a history row when metadata
        # is written
        
        # if the file exists, read the metadata that's in there
        if path.is_file():
            try:
                with zipfile.ZipFile(path, 'r', compression=zipfile.ZIP_DEFLATED) as f:
                    if 'pcot_metadata' in f.namelist():
                        d = f.read('pcot_metadata').decode('utf-8')
                        d = json.loads(d, object_hook=deserialiser)
                        self.metadata = Metadata.deserialise(d)
                    else:
                        self.metadata = Metadata(type=ArchiveType.UNKNOWN)  # existing archive, but there was no metadata!
                    # now we have loaded metadata, this will need to be added to history when
                    # we write.
            except Exception as e:
                logger.error(f"Error reading metadata from {path}: {e}")


    def open(self):
        self.zip = zipfile.ZipFile(self.path, self.mode.lower(), compression=zipfile.ZIP_DEFLATED)
        
        mode = self.mode.lower()

        if mode == 'a':
            # if we're doing append, now the file is open we should try to work out
            # the next array number.
            array_items = [x[5:] for x in self.zip.namelist() if x.startswith("ARAE-")]
            if len(array_items) > 0:
                self.arrayct = max([int(x) for x in array_items]) + 1

        # if we are writing: write the metadata, adding a line to the history
        # WE DON'T DO THIS WHEN APPENDING - it clutters the archive with dup names
        # (since we can't delete from zips)
        if mode == 'w':

            # move any existing metadata from the read in the constructor into the history.
            # Only do this if there was loaded metadata - we create a new row
            # in the history for that metadata, because we're about to set
            # newer metadata. Loaded data (any data that's been written to a file) will
            # have a date.
            if self.metadata.date is not None:
                self.metadata.save_history()

            # update the metadata
            self.metadata.update()
            self.writeJson("pcot_metadata",self.metadata.serialise())

        logger.debug(f"Opened {self}")

    def close(self):
        if self.zip is not None:
            self.zip.close()
            self.zip = None

    def __str__(self):
        return f"FileArchive({self.path, self.mode})"


class MemoryArchive(Archive):
    """
    Used for ZIP archives in memory
    """

    mode: bool      # 'r' or 'w', set by subclass
    id: int = 0     # unique ID for each archive

    def __init__(self, data=None, progressCallback=None):
        if data is None:
            data = BytesIO()
            mode = 'w'
        else:
            data = data
            mode = 'r'
        super().__init__(mode, progressCallback=progressCallback)
        self.data = data
        self.id = MemoryArchive.id
        MemoryArchive.id += 1

    def open(self):
        self.zip = zipfile.ZipFile(self.data, self.mode, compression=zipfile.ZIP_DEFLATED)
        logger.debug(f"Opened {self}")

    def close(self):
        if self.zip is not None:
            self.zip.close()
            self.zip = None

    def get(self) -> BytesIO:
        return self.data

    def __str__(self):
        return f"MemoryArchive(id={self.id}, {self.mode})"
