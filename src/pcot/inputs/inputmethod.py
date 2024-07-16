##
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any

from pcot import ui
from pcot.datum import Datum
from pcot.ui.canvas import Canvas

logger = logging.getLogger(__name__)


class InputMethod(ABC):
    """Defines a way of inputting data (image data, usually). Each input has several
    of this which are all always present, but only one is active (determined by
    its index in the Input).
    """

    input: 'Input'  # this may be None for an "orphan" input method which isn't connected to the document
    name: str
    data: Any
    showROIs: bool

    def __init__(self, inp):
        self.input = inp
        self.name = ''
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
                if self.data.isNone():  # it's still not there
                    logger.info("CACHE WAS INVALID AND DATA COULD NOT BE READ")
                else:
                    logger.info("CACHE WAS INVALID, DATA HAS BEEN READ")
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

    def getName(self):
        """to override - returns the name for display purposes"""
        return 'override-getName!'

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

