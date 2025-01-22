##
import fnmatch
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Any, List

from pcot import ui
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui.canvas import Canvas

logger = logging.getLogger(__name__)


class InputMethod(ABC):
    """Defines a way of inputting data (image data, usually). Each input has several
    of this which are all always present, but only one is active (determined by
    its index in the Input).
    """

    input: 'Input'  # this may be None for an "orphan" input method which isn't connected to the document
    data: Any
    showROIs: bool

    def __init__(self, inp):
        self.input = inp
        self.data = Datum.null
        Canvas.initPersistData(self)  # creates data inside the canvas
        self.showROIs = False  # used by the canvas

    def _document(self):
        return self.input.mgr.doc if self.input is not None else None

    def isActive(self):
        """Is this method active?"""
        return self.input.isActive(self)

    @abstractmethod
    def readData(self) -> Datum:
        """to override - actually runs the input and returns data. Do not call from anywhere but get().
        This HAS to be overridden."""
        pass

    def mark(self):
        """About to perform a change, so mark an undo point"""
        if self.input is not None:
            return self.input.mgr.doc.mark()

    def unmark(self):
        """remove most recently placed undo mark but do not transfer to redo stack (it was abandoned)"""
        if self.input is not None:
            return self.input.mgr.doc.unmark()

    def undo(self):
        """undo the entire document - widget has responsibility for updating UI"""
        if self.input is not None:
            self.input.mgr.doc.undo()

    def redo(self):
        """redo the entire document - widget has responsibility for updating UI"""
        if self.input is not None:
            self.input.mgr.doc.redo()

    def canUndo(self):
        if self.input is None:
            return False
        return self.input.mgr.doc.canUndo()

    def canRedo(self):
        if self.input is None:
            return False
        return self.input.mgr.doc.cando()

    def invalidate(self):
        """invalidates the method's cached data"""
        self.data = Datum.null

    def setInputException(self, e: Optional[str]):
        """Sets the input exception for this method"""
        if self.input is not None:
            self.input.exception = e
        if e is not None:
            ui.error(e)

    def get(self) -> Datum:
        """returns cached data - if that's None, attempts to read data and cache it."""
        if self.data is None:
            raise Exception("input methods should not return None from readData(), ever.")
        if self.data.isNone():   # data is none, try to read it and cache it
            self.setInputException(None)
            try:
                self.data = self.readData()  # this is a method in each subclass
                # a lot of debugging output
                name = f"{self.input.idx}:{self.getName()}"
                if self.isActive():
                    if self.data.isNone():  # it's still not there
                        logger.debug(f"{name}: ACTIVE METHOD - CACHE WAS INVALID AND DATA COULD NOT BE READ")
                    else:
                        logger.debug(f"{name}: ACTIVE METHOD - CACHE WAS INVALID, DATA HAS BEEN READ")
                else:
                    if self.data.isNone():  # it's still not there
                        logger.debug(f"{name}: Cache invalid, data not read for inactive method")
                    else:
                        logger.debug(f"{name}: CACHE WAS INVALID, DATA HAS BEEN READ FOR INACTIVE METHOD!!!")

            except FileNotFoundError as e:
                # this one usually doesn't happen except in a library
                self.setInputException(f"Cannot read file {e.filename}")
            except Exception as e:
                # this one does. It's annoying that we trap this exception; it's a bit of a catch-all and
                # when stuff fails further down the line, it's hard to know what went wrong. But we can
                # at least log a traceback here.
                logger.exception(e)
                self.setInputException(str(e))
        return self.data

    @abstractmethod
    def getName(self):
        """to override - returns the name for display purposes"""
        return 'override-getDisplayName!'

    @abstractmethod
    def createWidget(self):
        """to override - creates the editing widget in the input window. If not overriden, you won't get
        a button to select that input method (useful for DirectInputMethod)"""
        return None

    def serialise(self, internal):
        """to override - converts this object's state into a bunch of plain data
        which can be converted to JSON. See notes in document.py for "internal" - it really
        means we are not truly serialising, just constructing a memento for redo/undo.
        """
        return None

    def deserialise(self, data, internal):
        """to override - sets this method's data from JSON-read data"""
        raise Exception("InputMethod does not have a deserialise method")

    def modifyWithParameterDict(self, d: 'TaggedDict') -> bool:
        """to override - modifies the method with a set of parameters from a
        parameter file. Returns true if the method was modified, false if not."""
        # by default does nothing. Don't make it throw because it still gets
        # called on direct, null etc.
        return False

    def _getFilesFromParameterDict(self, d: 'TaggedDict') :
        """Helper method used to process the "filenames" batch parameter for input
        methods which use it - it's a list of UNIX filename patterns.
        Assume we have 'directory' in the tagged dict, and a tagged list of
        'filenames'. The output will be self.dir and self.files. """

        # get the directory and the files therein.

        self.dir = d.directory
        files_in_directory = os.listdir(self.dir)

        # each filename is actually a pattern - find filenames that match, sort them, then add them to file list
        # so that the sort order is alphabetic within the groups found for each pattern, but keeps the order
        # of the patterns.

        self.files = []
        if len(d.filenames) < 0:
            raise Exception(f"No filenames found in {self.getName()} input")
        for pattern in d.filenames:
            files_for_this_pattern = []
            logger.debug(f" Checking for wildcard match against {pattern}")
            for f in files_in_directory:
                # Filenames are UNIX patterns - we use fnmatch to match them. E.g. "*.bin" and not ".*\.bin"
                if fnmatch.fnmatch(f, pattern) and os.path.isfile(os.path.join(self.dir, f)):
                    logger.debug(f" {f} MATCH!!!!!")
                    files_for_this_pattern.append(f)
                logger.debug(f" {f}")
            if len(files_for_this_pattern) == 0:
                raise Exception(f"No files found matching: {pattern}")
            files_for_this_pattern.sort()
            logger.info(f"files found with pattern: {pattern}")
            self.files.extend(files_for_this_pattern)





