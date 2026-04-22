"""
User interface for editing tagged aggregates
"""

import itertools
from typing import List

from PySide2.QtCore import QEvent, Qt
from PySide2.QtWidgets import QGridLayout, QVBoxLayout, \
    QGroupBox, QLabel, QScrollArea, QWidget, QSizePolicy

from pcot.ui.collapser import CollapserSection
from pcot.ui.taggedaggregates.editors import createEditor

MINWIDTH = 700
MINHEIGHT = 500

class ScrollContent(QWidget):
    """
    A content widget whose sizeHint always reflects its layout,
    and which notifies the scroll area when its size changes.
    """
    def sizeHint(self):
        if self.layout() is not None:
            return self.layout().sizeHint()
        return super().sizeHint()

    def event(self, e):
        if e.type() == QEvent.LayoutRequest:
            self.updateGeometry()
        return super().event(e)



class AggregateEditorWidget(QWidget):
    """
    A reusable widget that lays out a TaggedDict for editing.
    Can be embedded in dialogs or standalone windows.
    """
    def __init__(self, d, handler=None, parent=None):
        super().__init__(parent)

        self.handler = handler
        self.ct = itertools.count()
        self.editors = []

        self.d = d.clone()      # operate on a clone
        self._data = None

        # Reasonable minimum size for the whole widget (dialog/window size)
        self.setMinimumSize(MINWIDTH, MINHEIGHT)

        layout = QVBoxLayout(self)

        # Scroll area
        scrollarea = QScrollArea()
        scrollarea.setWidgetResizable(True)
        scrollarea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scrollarea.setAlignment(Qt.AlignTop)  # keep content pinned to top
        layout.addWidget(scrollarea)

        # Content inside scroll area
        content = ScrollContent()
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        scrollarea.setWidget(content)

        contentLayout = QGridLayout()
        content.setLayout(contentLayout)

        # Populate the layout
        self.layoutDict(contentLayout, [], self.d)

        # Stretch at bottom so items gather at the top *within* the content
        contentLayout.setRowStretch(next(self.ct), 1)

    def data(self):
        return self.d

    def layoutDict(self, container: QGridLayout, path: List[str], d):
        """
        Lays out a TaggedDict in a container, creating subframes for sub-dicts.
        """
        for k, v in d.items():
            tag = d.tag(k)
            desc = tag.description

            if isinstance(v, type(d)):  # TaggedDict
                # Sub-dictionary builds a CollapserSection, or GroupBox at top level
                if len(path) == 0:
                    group = CollapserSection(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    layout = QGridLayout()
                    layout.setContentsMargins(20, 0, 0, 0)
                    self.layoutDict(layout, path + [k], v)
                    group.setContentLayout(layout, stretch=True)
                else:
                    group = QGroupBox(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    group.setMinimumWidth(MINWIDTH-100)
                    layout = QGridLayout()
                    self.layoutDict(layout, path + [k], v)
                    group.setLayout(layout)

                container.addWidget(group, next(self.ct), 0, 1, 2)

            else:
                # Leaf node builds an editor
                editor = createEditor(self, tag, d, k, self.handler)
                row = next(self.ct)
                container.addWidget(QLabel(editor.label), row, 0)
                container.addWidget(editor.widget, row, 1)
                self.editors.append((path + [k], editor.widget))


