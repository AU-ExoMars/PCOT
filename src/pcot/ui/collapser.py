"""Collapser: a list of collapsable sections in a scroll box.
    example usage:

        coll = Collapser()                  # create a collapser; may need to set min height.
        layout.addWidget(coll)              # add to a layout

        # now create layouts with widgets in them...

        ll = QtWidgets.QVBoxLayout()
        ll.addWidget(QtWidgets.QLabel("p1: label"))
        ll.addWidget(QtWidgets.QPushButton("p1: button"))

        # add each layout to the collapser

        coll.addSection("Section 1", ll)

        # finish with this, to create a big stretcher at the bottom

        coll.end()
"""

from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt


class ContentArea(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)


class CollapserSection(QtWidgets.QWidget):
    """This is a section within the collapsing list - the code comes from here: https://stackoverflow.com/a/56275050
    with a few modifications. We use setContentLayout to add layouts.

    Don't use this directly - use Collapser. """

    def __init__(self, title, parent=None, animationDuration=100, isOpen=False, isAlwaysOpen=False):
        super(CollapserSection, self).__init__(parent=parent)

        if isAlwaysOpen:
            isOpen = True
        self.isAlwaysOpen = isAlwaysOpen

        self.contentArea = ContentArea()

        if not isAlwaysOpen:
            self.animationDuration = animationDuration
            self.toggleAnimation = QtCore.QParallelAnimationGroup()
            self.headerLine = QtWidgets.QFrame()
            self.toggleButton = QtWidgets.QToolButton()
            toggleButton = self.toggleButton
            toggleButton.setStyleSheet("QToolButton { border: none; }")
            toggleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            toggleButton.setArrowType(QtCore.Qt.RightArrow)
            toggleButton.setText(str(title))
            toggleButton.setCheckable(True)
            toggleButton.setChecked(isOpen)

            headerLine = self.headerLine
            headerLine.setFrameShape(QtWidgets.QFrame.HLine)
            headerLine.setFrameShadow(QtWidgets.QFrame.Sunken)
            headerLine.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)

        self.contentArea.setStyleSheet("""
        QScrollArea { background-color: white; border: none; }
        """)
        self.contentArea.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                       QtWidgets.QSizePolicy.Minimum)

        if not isAlwaysOpen:
            # start out collapsed
            self.contentArea.setMaximumHeight(0)
            self.contentArea.setMinimumHeight(0)
            # let the entire widget grow and shrink with its content
            toggleAnimation = self.toggleAnimation
            toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
            toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
            toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self.contentArea, b"maximumHeight"))

        self.mainLayout = QtWidgets.QGridLayout()
        mainLayout = self.mainLayout
        # don't waste space
        mainLayout.setVerticalSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        if isAlwaysOpen:
            mainLayout.addWidget(self.contentArea, 0, 0, 1, 3)
        else:
            mainLayout.addWidget(self.toggleButton, 0, 0, 1, 1, QtCore.Qt.AlignLeft)
            mainLayout.addWidget(self.headerLine, 0, 2, 1, 1)
            mainLayout.addWidget(self.contentArea, 1, 0, 1, 3)

        self.setLayout(self.mainLayout)

        def start_animation(checked):
            arrow_type = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
            direction = QtCore.QAbstractAnimation.Forward if checked else QtCore.QAbstractAnimation.Backward
            toggleButton.setArrowType(arrow_type)
            self.toggleAnimation.setDirection(direction)
            self.toggleAnimation.start()

        if not isAlwaysOpen:
            self.toggleButton.clicked.connect(start_animation)
            if isOpen:
                start_animation(True)

    def setContentLayout(self, contentLayout):
        self.contentArea.destroy()
        self.contentArea.setLayout(contentLayout)
        self.contentArea.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        #        self.contentArea.adjustSize()
        #        self.contentArea.updateGeometry()

        contentHeight = contentLayout.sizeHint().height()

        if not self.isAlwaysOpen:
            collapsedHeight = self.sizeHint().height() - self.contentArea.maximumHeight()
            for i in range(self.toggleAnimation.animationCount() - 1):
                expandAnimation = self.toggleAnimation.animationAt(i)
                expandAnimation.setDuration(self.animationDuration)
                expandAnimation.setStartValue(collapsedHeight)
                expandAnimation.setEndValue(collapsedHeight + contentHeight)
            contentAnimation = self.toggleAnimation.animationAt(self.toggleAnimation.animationCount() - 1)
            contentAnimation.setDuration(self.animationDuration)
            contentAnimation.setStartValue(0)
            contentAnimation.setEndValue(contentHeight)


class Collapser(QtWidgets.QScrollArea):
    def __init__(self, parent=None, animationDuration=200, lrmargins=2, topmargin=2, bottommargin=2):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.secs = []
        self.w = QtWidgets.QWidget()
        self.setWidget(self.w)
        self.setWidgetResizable(True)
        self.layout = QtWidgets.QVBoxLayout()
        self.animationDuration = animationDuration
        self.w.setLayout(self.layout)
        self.layout.setContentsMargins(lrmargins, topmargin, lrmargins, bottommargin)

    def addSection(self, title, layout, isOpen=False, isAlwaysOpen=False):
        sec = CollapserSection(title, parent=self,
                               animationDuration=self.animationDuration,
                               isOpen=isOpen,
                               isAlwaysOpen=isAlwaysOpen)
        self.layout.addWidget(sec)
        self.secs.append(sec)
        sec.setContentLayout(layout)
        return sec

    def clear(self):
        # runs through the groups in reverse order (3,2,1..) to delete
        # each item by setting its parent to None. Except that doesn't work
        # on spacers, we need to do that a different way.
        for i in reversed(range(self.layout.count())):
            xx = self.layout.itemAt(i)
            if xx.spacerItem():
                self.layout.removeItem(xx)
            else:
                xx.widget().setParent(None)

    def end(self):
        self.layout.addStretch(10)
        self.adjustSize()
        self.updateGeometry()


class TestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("foo")
        self.w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self.w.setLayout(layout)
        self.setCentralWidget(self.w)
        layout.addWidget(QtWidgets.QLabel("sovsdf"))

        coll = Collapser()
        layout.addWidget(coll)

        ll = QtWidgets.QVBoxLayout()
        ll.addWidget(QtWidgets.QLabel("p1: label"))
        ll.addWidget(QtWidgets.QPushButton("p1: button"))
        coll.addSection("Section 1", ll)

        ll = QtWidgets.QGridLayout()
        for x in range(0, 20):
            ll.addWidget(QtWidgets.QLabel("p1: label"), x, 0)
            ll.addWidget(QtWidgets.QPushButton(f"p1: button {x}"), x, 1)
        coll.addSection("Section 2", ll)

        coll.end()

        self.show()


def test():
    return TestWindow()
