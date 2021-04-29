## @package ui.mplwidget
# a widget which can contain a Matplotlib figure
# See xformcurve for an example.
#
# This page is useful
# https://www.learnpyqt.com/courses/graphics-plotting/plotting-matplotlib/

from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.figure import Figure

## Matplotlib canvas class containing a single figure
class MplCanvas(Canvas):
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111) # make new one
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

## the matplotlib widget proper.
class MplWidget(QtWidgets.QWidget):
    ## widget constructor taking parent
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)   # Inherit from QWidget
        self.canvas = MplCanvas()                  # Create canvas object
        self.vbl = QtWidgets.QVBoxLayout()         # Set box for plotting
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.fig = self.canvas.fig # convenience
        self.ax = self.canvas.ax

    ## called when we want to save a figure
    def save(self):
        # I'd like to be able to add more options to the dialog,
        # but we're using the OS's dialog so No Can Do unless I
        # write a whole new save dialog (with a file system monitoring
        # thread)
        res = QtWidgets.QFileDialog.getSaveFileName(self, 'Save figure', '.',
          "Figures (*.png *.pdf *.jpg)")
        if res[0]!='':
            self.fig.savefig(res[0])

    ## clear all drawings
    def clear(self):
        self.ax.cla()
    ## force redraw
    def draw(self):
        self.canvas.draw()