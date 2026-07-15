## dictionary of name -> brush for connection pad drawing
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QLinearGradient

from pcot.datum import Datum
from pcot.datumtypes import Type

brushDict = {}

logger = logging.getLogger(__name__)


def register(t: Type, colOrBrush):
    """register a colour or brush to draw the connector for a datum type"""
    if isinstance(colOrBrush, QBrush):
        brushDict[t] = colOrBrush
    else:
        brushDict[t] = QBrush(colOrBrush)


def quickGrad(c1: QColor, c2: QColor, c3: QColor, finalC: QColor) -> QBrush:
    """creates a gradient consisting of three colours in quick succession
    followed by a wide band of another colour. Used to mark connections such as RGB."""
    grad = QLinearGradient(0, 0, 20, 0)
    grad.setColorAt(0, c1)
    grad.setColorAt(0.4, c2)
    grad.setColorAt(0.8, c3)
    grad.setColorAt(1, finalC)
    return QBrush(grad)


# register builtin types

register(Datum.ANY, Qt.GlobalColor.red)
register(Datum.IMG, Qt.GlobalColor.blue)
register(Datum.ROI, Qt.GlobalColor.cyan)
register(Datum.TABLE, Qt.GlobalColor.darkMagenta)
register(Datum.TESTRESULT, Qt.GlobalColor.darkYellow)
register(Datum.NUMBER, Qt.GlobalColor.darkGreen)
register(Datum.VARIANT, QBrush(Qt.GlobalColor.black, Qt.BrushStyle.DiagCrossPattern))
register(Datum.NONE, QBrush(Qt.GlobalColor.red, Qt.BrushStyle.BDiagPattern))

_unknown = QBrush(Qt.GlobalColor.magenta)


def getBrush(typeObject):
    """get a brush by datumtypes.Type subclass instance or magenta if no brush is found"""
    if typeObject in brushDict:
        return brushDict[typeObject]
    else:
        logger.error(f"Unknown type {typeObject}")
        return _unknown
