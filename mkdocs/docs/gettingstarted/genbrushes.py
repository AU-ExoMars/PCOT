from pcot import connbrushes
from pcot.datum import Datum
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtSvg import *

SIZE=64

def render(filename,b):
    img = QImage(SIZE,SIZE,QImage.Format.Format_RGB888)
    img.fill(Qt.GlobalColor.white)

    painter = QPainter(img)
    painter.setBrush(b)
    painter.drawRect(0,0,SIZE,SIZE)
    painter.end()

    img.save(filename)



for t in Datum.types:
    if t.connColour is not None or t in connbrushes.brushDict:
        render(f"conn_{t}.png",connbrushes.getBrush(t))
