"""a widget which can contain a Matplotlib figure
See xformcurve for an example.

This page is useful
https://www.learnpyqt.com/courses/graphics-plotting/plotting-matplotlib/
"""
import os

from PySide2 import QtWidgets

import matplotlib

import pcot

matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.figure import Figure


## Matplotlib canvas class containing a single figure
class MplCanvas(Canvas):
    def __init__(self):
        self.fig = Figure(figsize=(4, 2))
        self.create_default_subplot()
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

    def create_default_subplot(self):
        self.ax = self.fig.add_subplot(111)  # make new one



## the matplotlib widget proper.
class MplWidget(QtWidgets.QWidget):
    ## widget constructor taking parent
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)  # Inherit from QWidget
        self.canvas = MplCanvas()  # Create canvas object
        self.vbl = QtWidgets.QVBoxLayout()  # Set box for plotting
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.fig = self.canvas.fig  # convenience
        self.ax = self.canvas.ax    # ditto

    ## called when we want to save a figure
    def save(self):
        # I'd like to be able to add more options to the dialog,
        # but we're using the OS's dialog so No Can Do unless I
        # write a whole new save dialog (with a file system monitoring
        # thread)

        res = QtWidgets.QFileDialog.getSaveFileName(self, 'Save figure',
                                                    os.path.expanduser(pcot.config.getDefaultDir('mplplots')),
                                                    "Figures (*.png *.pdf *.jpg)",
                                                    options=pcot.config.getFileDialogOptions())
        if res[0] != '':
            path = res[0]
            self.fig.savefig(path)
            pcot.config.setDefaultDir('mplplots', os.path.dirname(os.path.realpath(path)))

    ## clear all drawings and recreate the default subplot
    def clear(self):
        self.fig.clf()
        self.canvas.create_default_subplot()
        self.ax = self.canvas.ax    # and reset convenience link

    ## force redraw
    def draw(self):
        self.fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
        self.canvas.draw()
