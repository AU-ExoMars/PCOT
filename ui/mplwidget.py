from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')

# This page is useful
# https://www.learnpyqt.com/courses/graphics-plotting/plotting-matplotlib/

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.figure import Figure

# Matplotlib canvas class containing a single figure
class MplCanvas(Canvas):
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111) # make new one
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

# matplotlib widget.
class MplWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)   # Inherit from QWidget
        self.canvas = MplCanvas()                  # Create canvas object
        self.vbl = QtWidgets.QVBoxLayout()         # Set box for plotting
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.fig = self.canvas.fig # convenience
        self.ax = self.canvas.ax
