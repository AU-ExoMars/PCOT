"""
Data widget that shows either a text view or a canvas view of the data.
"""

from PySide6 import QtWidgets

from pcot.ui.canvas import Canvas
from pcot.utils import SignalBlocker
from pcot.utils.text import generateIndenting


class DataWidget(QtWidgets.QWidget):
    DATA = 0
    SOURCES = 1

    def __init__(self, parent, source_section=False):
        super().__init__(parent)

        outer = QtWidgets.QVBoxLayout(self)
        self.setLayout(outer)

        # contains the source and item type widgets
        inner = QtWidgets.QHBoxLayout()
        lab = QtWidgets.QLabel("Type:")
        inner.addWidget(lab)
        self.typeEdit = QtWidgets.QLineEdit()
        self.typeEdit.setReadOnly(True)
        inner.addWidget(self.typeEdit)
        self.dispTypeCombo = QtWidgets.QComboBox()
        self.dispTypeCombo.addItem("Data")
        self.dispTypeCombo.addItem("Sources")
        self.dispTypeCombo.currentIndexChanged.connect(self.dispTypeChanged)
        inner.addWidget(self.dispTypeCombo)

        # only add that inner layout if we want to display source and type
        if source_section:
            outer.addLayout(inner)

        self.canvas = Canvas(self)
        self.text = QtWidgets.QTextEdit(self)
        outer.addWidget(self.canvas)
        outer.addWidget(self.text)
        self.text.setVisible(False) # either the canvas or text will become visible..

        self.dispType = self.DATA
        self.datum = None

    def dispTypeChanged(self, i):
        self.dispType = i
        self.refresh()

    def display(self, d):
        self.datum = d
        self.refresh()

    def refresh(self):
        d = self.datum
        if self.datum is None:
            self.text.setText("No data present")
            self.typeEdit.setText("unconnected")
            canvVis = False
        else:
            self.typeEdit.setText(str(d.tp))
            if self.dispType == self.SOURCES:
                self.text.setText(generateIndenting(d.sources.long()))
                canvVis = False
            elif d.isImage():
                self.canvas.display(d.val)
                canvVis = True
            else:
                self.text.setText(str(d.val))
                canvVis = False

        self.canvas.setVisible(canvVis)
        self.text.setVisible(not canvVis)

        with SignalBlocker(self.dispTypeCombo):
            self.dispTypeCombo.setCurrentIndex(self.dispType)
