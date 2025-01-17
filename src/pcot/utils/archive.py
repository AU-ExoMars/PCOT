import json
from pathlib import Path
from typing import Callable, Union

import numpy as np
import zipfile
from io import BytesIO


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
        if self.mode != 'r':
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
        name = "ARAE-{}".format(self.arrayct)
        self.writeArray(name, a)
        self.arrayct += 1
        return name

    def writeStr(self, name: str, string: str, permit_replace=False):
        if self.zip is None:
            raise Exception("Archive is not open")
        self.assert_write()
        print(f"Writing to {name}")
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
        s = json.dumps(d, sort_keys=True, indent=4)
        self.writeStr(name, s, permit_replace=permit_replace)

    def readJson(self, name):
        if self.zip is None:
            raise Exception("Archive is not open")
        s = self.readStr(name)
        d = json.loads(s)
        d = self.convertTagsToArrays(d)
        return d

    def getNames(self):
        return self.zip.namelist()


class FileArchive(Archive):
    """
    Used for ZIP files on disk.
    """

    def __init__(self, path: Union[Path,str], mode='r',  progressCallback: Callable[[str], None] = None):
        """Open a Zip archive on disk.
        The mode is 'r' for read, 'w' for write, and 'a' for append.
        """
        assert mode in ['r', 'w', 'a']
        super().__init__(mode, progressCallback=progressCallback)
        self.path = path

    def open(self):
        self.zip = zipfile.ZipFile(self.path, self.mode.lower(), compression=zipfile.ZIP_DEFLATED)

        if self.mode.lower() == 'a':
            # if we're doing append, now the file is open we should try to work out
            # the next array number.
            array_items = [x[5:] for x in self.zip.namelist() if x.startswith("ARAE-")]
            if len(array_items) > 0:
                self.arrayct = max([int(x) for x in array_items]) + 1

    def close(self):
        if self.zip is not None:
            self.zip.close()
            self.zip = None


class MemoryArchive(Archive):
    """
    Used for ZIP archives in memory
    """

    mode: bool      # 'r' or 'w', set by subclass

    def __init__(self, data=None, progressCallback=None):
        if data is None:
            data = BytesIO()
            mode = 'w'
        else:
            data = data
            mode = 'r'
        super().__init__(mode, progressCallback=progressCallback)
        self.data = data

    def open(self):
        self.zip = zipfile.ZipFile(self.data, self.mode, compression=zipfile.ZIP_DEFLATED)

    def close(self):
        if self.zip is not None:
            self.zip.close()
            self.zip = None

    def get(self) -> BytesIO:
        return self.data
