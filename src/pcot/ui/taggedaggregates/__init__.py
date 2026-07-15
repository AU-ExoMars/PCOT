"""
User interface for editing tagged aggregates
"""

import itertools
from typing import List

from PySide6.QtCore import QEvent, Qt, QSize
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, \
    QGroupBox, QLabel, QScrollArea, QWidget, QSizePolicy, QSpacerItem, QScrollBar, QAbstractScrollArea, QLayout, \
    QDialog, QDialogButtonBox, QMessageBox

from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui.collapser import CollapserSection
from pcot.ui.taggedaggregates.editors import createEditor

MINWIDTH = 700
MINHEIGHT = 500

class ScrollContent(QWidget):
    """
    This is a widget with some kind of strategy for getting a size hint. What that
    is is something I'm struggling with.
    """
    # def sizeHint(self):
    #     """Vertically as big as possible; really don't do this """
    #     hint = super().sizeHint()
    #     hint.setHeight(1000)
    #     return hint

    # def sizeHint(self):
    #     """The size hint is that of the layout if there is one"""
    #     if self.layout() is not None:
    #         print(f"size hint: {self.layout().sizeHint()}")
    #         return self.layout().sizeHint()
    #     return super().sizeHint()
    def sizeHint(self):
        """The size hint is the sum of the hints of the layout's contents"""
        hint = super().sizeHint()

        if self.layout() and self.layout().count():
            hs = [self.layout().itemAt(i).widget().sizeHint().height() for i in range(self.layout().count())]
            rows_h = sum(hs)
            # print(f"Row heights inside ScrollContent: {','.join(map(str, hs))}")
        else:
            return hint

        # print(f"ScrollContent Previous hint: {hint}")
        min_h = rows_h + 20
        hint.setHeight(max(100, min_h))
        # print(f"ScrollContent New hint: {hint}, min_h: {min_h}")
        return hint

    def event(self, e):
        if e.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()
        return super().event(e)



class AggregateEditorWidget(QWidget):
    """
    A reusable widget that lays out a TaggedDict for editing.
    Can be embedded in dialogs or standalone windows.

    d: dictionary to edit
    handler: something that is called every time an editor changes value (has onPreChange and onPostChange),
        typically used for undo
    internal_editor: This editor is embedded as a widget within another attribute editor or dialog, so should
        be as small as possible and not have a collapser. If this is False, it will often be too wide to
        usefully embed!
    suppress_single_key: if the dict to be laid out has only one key, don't make a label for that key. A hack.
    """
    def __init__(self, d, handler=None, parent=None, internal_editor=False, suppress_single_key_label=False):
        super().__init__(parent)

        self.internal_editor = internal_editor
        self.handler = handler
        self.ct = itertools.count()
        self.editors = []

        self.d = d if internal_editor else d.clone()      # operate on a clone if this is the root editor
        self.suppress_single_key_label = suppress_single_key_label
        self._data = None

        # Reasonable minimum size for the whole widget (dialog/window size)
        if not self.internal_editor:
            self.setMinimumSize(MINWIDTH, MINHEIGHT)

        layout = QVBoxLayout(self)

        # Scroll area
        scrollarea = QScrollArea()
        scrollarea.setWidgetResizable(True)
        scrollarea.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scrollarea.setAlignment(Qt.AlignmentFlag.AlignTop)  # keep content pinned to top
        layout.addWidget(scrollarea)

        # Content inside scroll area
        self.content = ScrollContent()
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scrollarea.setWidget(self.content)

        self.contentLayout = QGridLayout()
        self.content.setLayout(self.contentLayout)

        # Populate the layout
        self.layoutDict(self.contentLayout, [], self.d)

        # Stretch at bottom so items gather at the top *within* the content
        self.contentLayout.setRowStretch(next(self.ct), 1)

    def sizeHint(self):
        h = self.content.sizeHint()
#        print(f"AggregateEditorWidget.sizeHint: {h}")
        return h

    def data(self):
        return self.d

    def layoutDict(self, container: QGridLayout, path: List[str], d):
        """
        Lays out a TaggedDict  in a container, creating subframes for sub-dicts.
        """

        for k, v in d.items():
            tag = d.tag(k)
            desc = tag.description

            if isinstance(v, TaggedDict):  # TaggedDict
                # Sub-dictionary builds a CollapserSection, or GroupBox at top level
                if len(path) == 0 and not self.internal_editor:
                    group = CollapserSection(desc)
                    group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    layout = QGridLayout()
                    layout.setContentsMargins(20, 0, 0, 0)
                    self.layoutDict(layout, path + [k], v)
                    group.setContentLayout(layout, stretch=True)
                else:
                    group = QGroupBox(desc)
                    group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    group.setMinimumWidth(MINWIDTH-100)
                    layout = QGridLayout()
                    self.layoutDict(layout, path + [k], v)
                    group.setLayout(layout)

                container.addWidget(group, next(self.ct), 0, 1, 2)

            else:
                # Leaf node builds an editor
                editor = createEditor(self, tag, d, k, self.handler)
                row = next(self.ct)
                if not self.suppress_single_key_label or len(d)>1:
                    # Here, if there's only one key in the dict, we don't show the label if
                    # suppress_single_key_label is true.
                    container.addWidget(QLabel(editor.label), row, 0)
                    container.addWidget(editor.widget, row, 1)
                else:
                    container.addWidget(editor.widget, row, 0)
                self.editors.append((path + [k], editor.widget))


class AggregateEditorDialog(QDialog):
    """
    A dialog wrapper around an tagged aggregate editor widget.
    Takes a validator function which returns None if all is well or an error string.
    """
    def __init__(self, d, validator_func=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.validator_func = validator_func
        layout = QVBoxLayout(self)

        # Embed the widget
        self.widget = AggregateEditorWidget(d, self)
        layout.addWidget(self.widget)

        # OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._data = None

    def validate_accept(self):
        if self.validator_func:
            possible_error = self.validator_func(self.widget.data())
            if possible_error:
                QMessageBox.critical(self, "Validation error", possible_error)
                return
        self.accept()

    def accept(self):
        self._data = self.widget.data()
        super().accept()

    def data(self):
        return self._data
