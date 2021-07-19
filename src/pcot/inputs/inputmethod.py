## defines a way of inputting data (image data, usually). Each input has several
# of this which are all always present, but only one is active (determined by
# its index in the Input).
from typing import Optional, Any

from pcot import ui
from pcot.ui.canvas import Canvas


class InputMethod:
    def __init__(self, inp):
        self.input = inp
        self.name = ''
        self.data = None
        Canvas.initPersistData(self)
        self.showROIs = False  # used by the canvas

    ## asks the input if I'm active
    def isActive(self):
        return self.input.isActive(self)

    ## to override - actually runs the input and returns data.
    def readData(self) -> Optional[Any]:
        return None

    def mark(self):
        """About to perform a change, so mark an undo point"""
        return self.input.mgr.graph.doc.mark()

    def unmark(self):
        """remove most recently placed undo mark but do not transfer to redo stack (it was abandoned)"""
        return self.input.mgr.graph.doc.unmark()

    def undo(self):
        """undo the entire document - widget has responsibility for updating UI"""
        self.input.mgr.graph.doc.undo()

    def redo(self):
        """redo the entire document - widget has responsibility for updating UI"""
        self.input.mgr.graph.doc.redo()

    def canUndo(self):
        return self.input.mgr.graph.doc.canUndo()

    def canRedo(self):
        return self.input.mgr.graph.doc.cando()

    ## invalidates
    def invalidate(self):
        self.data = None
        try:
            self.read()  # and try to read. TODO - I'm not happy about this; I feel it's happening too much. Too tired to think properly about it now.
        except FileNotFoundError as e:
            ui.error("Cannot read file {}".format(e.filename))
        except Exception as e:
            ui.error(str(e))

    ##  returns the cached data
    def get(self):
        return self.data

    ## reads the data if the cache has been invalidated
    def read(self):
        if self.data is None:
            self.data = self.readData()
            if self.data is not None:
                print("CACHE WAS INVALID, DATA MAY HAVE BEEN READ")

    ## to override - returns the name for display purposes
    def getName(self):
        return ''

    ## to override - creates the editing widget in the input window
    def createWidget(self):
        pass

    ## to override - converts this object's state into a bunch of plain data
    # which can be converted to JSON. See notes in document.py for "internal" - it really
    # means we are not truly serialising, just constructing a memento for redo/undo.
    def serialise(self, internal):
        return None

    ## to override - sets this method's data from JSON-read data
    def deserialise(self, data, internal):
        raise Exception("InputMethod does not have a deserialise method")

