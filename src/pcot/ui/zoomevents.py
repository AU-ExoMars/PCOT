"""Helpers which turn mouse wheel and trackpad pinch events into zoom factors, shared by the zoomable
views (graph, canvas, linear set). Each view does its own zooming; these just decide how much.

All factors returned are magnifications: greater than 1 zooms in, less than 1 zooms out.
"""
from typing import Optional

from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt


def wheelZoomFactor(evt: QtGui.QWheelEvent, step: float) -> Optional[float]:
    """Return the magnification for a wheel event, where `step` is the magnification for one
    standard mouse wheel notch (an angle delta of 120). Trackpads (notably on macOS) send a
    stream of many small deltas, some of which have no vertical component at all, so the zoom
    has to be proportional to the delta rather than a fixed step per event. Returns None for
    events with no vertical component, which should not zoom at all."""
    dy = evt.angleDelta().y()
    if dy == 0:
        return None
    return step ** (dy / 120.0)


def pinchZoomFactor(evt: QtCore.QEvent) -> Optional[float]:
    """If this is a trackpad pinch gesture event, return its magnification, otherwise None."""
    if evt.type() == QtCore.QEvent.Type.NativeGesture and \
            evt.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
        return 1.0 + evt.value()
    return None
