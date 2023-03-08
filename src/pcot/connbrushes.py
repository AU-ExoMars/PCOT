## dictionary of name -> brush for connection pad drawing
import logging

from PySide2.QtCore import Qt
from PySide2.QtGui import QColor, QBrush, QLinearGradient

from pcot.datum import Datum, Type

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
    return grad


# register builtin types

register(Datum.ANY, Qt.red)
register(Datum.IMGRGB, quickGrad(Qt.red, Qt.green, Qt.blue, QColor(50, 50, 50)))
register(Datum.IMG, Qt.blue)
register(Datum.ELLIPSE, Qt.cyan)
register(Datum.ROI, Qt.cyan)
register(Datum.DATA, Qt.darkMagenta)
register(Datum.NUMBER, Qt.darkGreen)
register(Datum.VARIANT, QBrush(Qt.black, Qt.DiagCrossPattern))
register(Datum.NONE, QBrush(Qt.red, Qt.BDiagPattern))

_unknown = QBrush(Qt.magenta)


def getBrush(typename):
    """get a brush by name or magenta if no brush is found"""
    if typename in brushDict:
        return brushDict[typename]
    else:
        logger.error(f"Unknown type {typename}")
        return _unknown
