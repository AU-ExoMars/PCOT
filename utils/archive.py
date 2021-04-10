
import json
import os
import shutil
import tempfile

import numpy as np
import zipfile
from io import BytesIO

import ui


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
    def __init__(self, mode='r'):
        self.mode = mode
        self.arrayct = 0
        self.zip = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.zip is not None:
            self.zip.close()
            self.zip = None

    def writeArray(self, name: str, a: np.ndarray):
        if self.zip is None:
            raise Exception("Archive is not open")
        b = BytesIO()
        np.save(b, a)
        print("Array written as {}".format(name))
        self.zip.writestr(name, b.getvalue())

    def writeArrayAndGenerateName(self, a: np.ndarray):
        name = "ARAE-{}".format(self.arrayct)
        self.writeArray(name, a)
        self.arrayct += 1
        return name

    def writeStr(self, name: str, string: str):
        if self.zip is None:
            raise Exception("Archive is not open")
        # I'm aware it'll do the encoding anyway, but I wanted to make it explicit
        self.zip.writestr(name, string.encode('utf-8'))

    def readArray(self, name: str) -> np.ndarray:
        if self.zip is None:
            raise Exception("Archive is not open")
        b = self.zip.read(name)
        bio = BytesIO(b)
        a = np.load(bio)
        return a

    def readStr(self, name: str) -> str:
        if self.zip is None:
            raise Exception("Archive is not open")
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
            return self.readArray(d)
        else:
            return d

    def writeJson(self, name, d):
        if self.zip is None:
            raise Exception("Archive is not open")
        d = self.convertArraysToTags(d)
        s = json.dumps(d, sort_keys=True, indent=4)
        self.writeStr(name, s)

    def readJson(self, name):
        if self.zip is None:
            raise Exception("Archive is not open")
        s = self.readStr(name)
        d = json.loads(s)
        d = self.convertTagsToArrays(d)
        return d


class FileArchive(Archive):
    """
    Used for ZIP files on disk
    """
    def __init__(self, name, mode='r'):
        self.mode = mode
        self.name = name
        self.arrayct = 0

    def __enter__(self):
        if self.mode == 'w':
            self.tempdir = tempfile.mkdtemp()
            self.tempfilename = os.path.join(self.tempdir,'temp.pcot')
            self.zip = zipfile.ZipFile(self.tempfilename, self.mode, compression=zipfile.ZIP_DEFLATED)
        else:
            self.zip = zipfile.ZipFile(self.name, self.mode, compression=zipfile.ZIP_DEFLATED)
        return self

    def __exit__(self, tp, value, traceback):
        if self.zip is not None:
            self.zip.close()
            self.zip = None
            if self.mode == 'w':
                if tp is None:  # we ONLY write the destination archive if there were no exceptions!
                    shutil.move(self.tempfilename, self.name)
                else:
                    ui.warn("File did not save due to an exception.")
                shutil.rmtree(self.tempdir)


class MemoryArchive(Archive):
    """
    Used for ZIP archives in memory
    """
    def __init__(self, data=None):
        if data is None:
            self.data = BytesIO()
            self.mode = 'w'
        else:
            self.data = data
            self.mode = 'r'
        self.arrayct = 0

    def __enter__(self):
        pass
        self.zip = zipfile.ZipFile(self.data, self.mode, compression=zipfile.ZIP_DEFLATED)
        return self

    def get(self) -> BytesIO:
        return self.data
