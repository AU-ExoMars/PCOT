from PySide2.QtCore import Qt, QRect
from PySide2.QtGui import QPainter
from typing import Callable, Tuple, List


class Annotation:
    def __init__(self):
        pass

    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        pass


class TestAnnotation(Annotation):
    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        p.setPen(Qt.yellow)
        p.setBrush(Qt.yellow)

        # now for the important bit...

        # DIVIDE by scale to get canvas width/heights
        # use mapcoords to get canvas coords.

        cx, cy = mapcoords(20, 20)

        # inspections off because these should be float, but drawRect expects int.
        # noinspection PyTypeChecker
        p.drawRect(cx, cy, 40 / scale, 40 / scale)

        cx, cy = mapcoords(20, 10)
        # noinspection PyTypeChecker
        r = QRect(cx, cy, 100 / scale, 10 / scale)
        p.drawText(r, Qt.AlignLeft | Qt.AlignBottom, "Hello World")


def draw(p: QPainter, annotations: List[Annotation], scale: float,
         mapcoords: Callable[[float, float], Tuple[float, float]]):
    for ann in annotations:
        ann.annotate(p, scale, mapcoords)
