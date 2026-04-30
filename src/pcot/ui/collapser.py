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

from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import Qt

class ContentArea(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)


class CollapserSection(QtWidgets.QWidget):
    """This is a section within the collapsing list - the code comes from here: https://stackoverflow.com/a/56275050
    with a few modifications. We use setContentLayout to add layouts.

    Don't use this directly - use Collapser. Actually, that's a lie
    right now - ConfigDialog uses it."""

    def __init__(self, title, parent=None, animationDuration=100, isOpen=False, isAlwaysOpen=False):
        super(CollapserSection, self).__init__(parent=parent)

        if isAlwaysOpen:
            isOpen = True

        self.isAlwaysOpen = isAlwaysOpen
        self.isNowOpen = isOpen
        self.contentArea = ContentArea()
        self.contentLayout = None

        if not isAlwaysOpen:
            self.animationDuration = animationDuration
            self.toggleAnimation = QtCore.QParallelAnimationGroup()
            self.headerLine = QtWidgets.QFrame()
            toggleButton = QtWidgets.QToolButton()
            toggleButton.setStyleSheet("QToolButton { border: none; }")
            toggleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            toggleButton.setArrowType(QtCore.Qt.RightArrow)
            toggleButton.setText(str(title))
            toggleButton.setCheckable(True)
            toggleButton.setChecked(isOpen)
            self.toggleButton = toggleButton

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
            self.toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
            self.toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
            self.toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self.contentArea, b"maximumHeight"))

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

        if not isAlwaysOpen:
            self.toggleButton.clicked.connect(self.toggleSectionOpen)
            if isOpen:
                self.toggleSectionOpen(True)

    def toggleSectionOpen(self, open):
        arrow_type = QtCore.Qt.DownArrow if open else QtCore.Qt.RightArrow
        direction = QtCore.QAbstractAnimation.Forward if open else QtCore.QAbstractAnimation.Backward
        self.toggleButton.setArrowType(arrow_type)
        self.toggleAnimation.setDirection(direction)
        self.toggleAnimation.start()
        self.isNowOpen = open

    def forceOpen(self):
        if not self.isNowOpen:
            self.toggleSectionOpen(True)

    def forceClose(self):
        if self.isNowOpen:
            self.toggleSectionOpen(False)

    def setContentLayout(self, contentLayout, stretch=False):
        """Used to set the layout of the collapser's content section. If stretch is true, the size policy
        will expand contents horizontally. We don't do that for palettes, because the buttons should be small."""
        self.contentArea.destroy()
        self.contentArea.setLayout(contentLayout)
        self.contentArea.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding if stretch else QtWidgets.QSizePolicy.Maximum,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.contentLayout = contentLayout
        self.resetContentHeight()

    def resetContentHeight(self):
        contentHeight = self.contentLayout.sizeHint().height()

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

            # a VERY hacky solution to the problem of the collapser section containing (directly or indirectly) lists which
            # shrink and expand. Whenever we call this, and the section is open, quickly close it and reopen it.
            if self.isNowOpen:
                self.forceClose()
                self.forceOpen()


    def updateGeometry(self):
        self.resetContentHeight()
        super().updateGeometry()


class Collapser(QtWidgets.QScrollArea):
    def __init__(self, parent=None, animationDuration=200, lrmargins=2, topmargin=2, bottommargin=2):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.animationDuration = animationDuration
        self.margins = (lrmargins, topmargin, lrmargins, bottommargin)
        self.w = None
        self.layout = None
        self.sectionsByName = {}
        self.clear()

    def clear(self):
        """Used to both initialise and reinitialise a collapser by just recreating its innards"""
        self.w = QtWidgets.QWidget()
        self.setWidget(self.w)
        self.setWidgetResizable(True)
        self.layout = QtWidgets.QVBoxLayout()
        self.w.setLayout(self.layout)
        self.layout.setContentsMargins(*self.margins)

    def addSection(self, title, layout, isOpen=False, isAlwaysOpen=False):
        sec = CollapserSection(title, parent=self,
                               animationDuration=self.animationDuration,
                               isOpen=isOpen,
                               isAlwaysOpen=isAlwaysOpen)
        self.layout.addWidget(sec)
        sec.setContentLayout(layout)
        self.sectionsByName[title] = sec
        return sec

    def setSectionVisible(self, sec_name, visible):
        self.sectionsByName[sec_name].setVisible(visible)

    def forceOpen(self, sec_name):
        self.sectionsByName[sec_name].forceOpen()

    def end(self):
        self.layout.addStretch(10)
        self.adjustSize()
        self.updateGeometry()

    def shouldCollapseWhenButtonClicked(self):
        # what would happen if we clicked the expandCollapse button?
        # if any sections are open, collapse all. Otherwise expand all.
        return any(x.isNowOpen for x in self.sectionsByName.values())

    def collapseExpandAll(self):
        collapse = self.shouldCollapseWhenButtonClicked()
        for sec in self.sectionsByName.values():
            if collapse:
                sec.forceClose()
            else:
                sec.forceOpen()
