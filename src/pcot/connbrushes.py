## Brushes for connection pad drawing. Each datum type describes its connector with plain colour
## and pattern strings (connColour and connPattern in datumtypes.Type) so that the types don't
## need Qt; this module turns those into QBrushes.
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QLinearGradient

from pcot.datumtypes import Type

# type -> brush; holds both brushes built from a type's description and those registered explicitly
brushDict = {}

logger = logging.getLogger(__name__)


def register(t: Type, colOrBrush):
    """register a colour or brush to draw the connector for a datum type, overriding the type's
    connColour and connPattern. Only needed for brushes those can't describe, such as gradients."""
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


_unknown = QBrush(Qt.GlobalColor.magenta)


def _makeBrush(t: Type):
    """build a brush from a type's connColour and connPattern, or return None if it doesn't have one"""
    if t.connColour is None:
        return None
    col = QColor(t.connColour)
    if not col.isValid():
        logger.error(f"Invalid connector colour '{t.connColour}' for type {t}")
        return None
    if t.connPattern is None:
        return QBrush(col)
    try:
        style = Qt.BrushStyle[t.connPattern]
    except KeyError:
        logger.error(f"Invalid connector pattern '{t.connPattern}' for type {t}")
        return QBrush(col)
    return QBrush(col, style)


def getBrush(typeObject):
    """get a brush by datumtypes.Type subclass instance or magenta if no brush is found.
    The brush is shared, so copy it before modifying it."""
    if typeObject not in brushDict:
        b = _makeBrush(typeObject)
        if b is None:
            logger.error(f"No connector brush for type {typeObject}")
            return _unknown
        brushDict[typeObject] = b
    return brushDict[typeObject]
