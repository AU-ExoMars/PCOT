##
from typing import Optional, Any

from pcot import ui
from pcot.ui.canvas import Canvas


class InputMethod:
    """Defines a way of inputting data (image data, usually). Each input has several
    of this which are all always present, but only one is active (determined by
    its index in the Input)."""
    def __init__(self, inp):
        self.input = inp
        self.name = ''
        self.data = None
        Canvas.initPersistData(self)  # creates data inside the canvas
        self.showROIs = False  # used by the canvas

    def isActive(self):
        """Is this method active?"""
        return self.input.isActive(self)

    def readData(self) -> Optional[Any]:
        """to override - actually runs the input and returns data."""
        return None

    def mark(self):
        """About to perform a change, so mark an undo point"""
        return self.input.mgr.doc.mark()

    def unmark(self):
        """remove most recently placed undo mark but do not transfer to redo stack (it was abandoned)"""
        return self.input.mgr.doc.unmark()

    def undo(self):
        """undo the entire document - widget has responsibility for updating UI"""
        self.input.mgr.doc.undo()

    def redo(self):
        """redo the entire document - widget has responsibility for updating UI"""
        self.input.mgr.doc.redo()

    def canUndo(self):
        return self.input.mgr.doc.canUndo()

    def canRedo(self):
        return self.input.mgr.doc.cando()

    def invalidate(self):
        """invalidates the method's cached data"""
        self.data = None

    def get(self):
        """returns cached data - if that's None, attempts to read data and cache it."""
        if self.data is None:
            self.input.exception = None
            try:
                self.data = self.readData()
                if self.data is None:
                    print("CACHE WAS INVALID AND DATA COULD NOT BE READ")
                else:
                    print("CACHE WAS INVALID, DATA HAS BEEN READ")
            except FileNotFoundError as e:
                # this one usually doesn't happen
                self.input.exception = str("Cannot read file {}".format(e.filename))
                ui.error(self.input.exception)
            except Exception as e:
                # this one does.
                self.input.exception = str(e)
                ui.error(self.input.exception)
        return self.data

    def getName(self):
        """to override - returns the name for display purposes"""
        return ''

    def createWidget(self):
        """to override - creates the editing widget in the input window"""
        pass

    def serialise(self, internal):
        """to override - converts this object's state into a bunch of plain data
        which can be converted to JSON. See notes in document.py for "internal" - it really
        means we are not truly serialising, just constructing a memento for redo/undo.
        """
        return None

    ## to override - sets this method's data from JSON-read data
    def deserialise(self, data, internal):
        raise Exception("InputMethod does not have a deserialise method")

