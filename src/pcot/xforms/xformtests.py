import dataclasses
import logging
import math
from dataclasses import dataclass
import random
from typing import List, Any, Tuple

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import QModelIndex, Signal, Qt
from PySide2.QtGui import QColor, QIntValidator, QDoubleValidator
from PySide2.QtWidgets import QMessageBox

import pcot
from pcot import ui, dq
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.sources import nullSourceSet
from pcot.ui.tablemodel import TableModelDataClass, ComboBoxDelegate, DQDelegate, DQDialog
from pcot.utils.annotations import IndexedPointAnnotation
from pcot.value import Value
from pcot.xform import XFormType, xformtype, XFormException
from pcot.xforms.tabdata import TabData

logger = logging.getLogger(__name__)


COLOURS = ['red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'black', 'white']

@dataclass
class PixTest:
    x: int = 0
    y: int = 0
    band: int = 0
    n: float = 0
    u: float = 0
    dq: int = 0  # really an np.uint16 but that doesn't serialise
    col: str = 'red'

    def val(self):
        return Value(self.n, self.u, np.uint16(self.dq))

    def test(self, val):
        return self.val().approxeq(val)

    @staticmethod
    def getHeader():
        return ['X', 'Y', 'band', 'N', 'U', 'DQ', 'col']

    def serialise(self):
        return dataclasses.astuple(self)

    @staticmethod
    def deserialise(t):
        return PixTest(*t)


class Model(TableModelDataClass):
    changed = Signal()

    def __init__(self, tab, _data: List[PixTest]):
        super().__init__(tab, PixTest, _data, True)
        self.failed = set()

    def data(self, index, role):
        if role == Qt.DisplayRole:
            r = index.row()
            c = index.column()
            if r == PixTest.getHeader().index('DQ'):
                dqv = self.d[c].dq
                return dq.chars(dqv)

        return super().data(index, role)

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview or any item delegates"""
        if index.isValid():
            self.tab.mark()  # we do the undo mark here, before the data is changed
            item, field = self.getItemAndField(index)
            d = self.d[item]

            def conv_to_non_negative_int(v, prev):
                """convert to non-negative integer:
                Convert a value to integer - if it is negative return the default value (the previous value in the
                node) otherwise return the new value."""
                v = int(v)
                if v >= 0:
                    return v
                else:
                    return prev

            try:
                if field == 0:
                    d.x = conv_to_non_negative_int(value, d.x)
                elif field == 1:
                    d.y = conv_to_non_negative_int(value, d.y)
                elif field == 2:
                    d.band = conv_to_non_negative_int(value, d.band)
                elif field == 3:
                    d.n = float(value)
                elif field == 4:
                    d.u = float(value)
                elif field == 5:
                    d.dq = conv_to_non_negative_int(value, d.dq)
                elif field == 6:
                    d.col = value

                # tell the view we changed
                self.dataChanged.emit(index, index, (QtCore.Qt.DisplayRole,))
                # and tell any other things too (such as the tab!)
                self.changed.emit()
            except ValueError:
                ui.log("Bad value type")
            return True
        return False

    def isFailed(self, item):
        return item in self.failed

    def changePos(self, item, x, y):
        if 0 <= item < len(self.d):
            self.d[item].x = x
            self.d[item].y = y
            self.dataChanged.emit(QModelIndex(), QModelIndex(), (QtCore.Qt.DisplayRole,))
            self.changed.emit()

    def add_random(self, chans, w, h):
        x = random.randrange(0, w)
        y = random.randrange(0, h)
        for i in range(0, chans):
            item = self.add_item()
            self.d[item] = PixTest(x, y, i, 0, 0, 0, random.choice(COLOURS))
        self.dataChanged.emit(QModelIndex(), QModelIndex(), (QtCore.Qt.DisplayRole,))
        self.changed.emit()


@xformtype
class XFormPixTest(XFormType):
    """Used in testing, but may be useful for running automated tests for users. Contains
    a table of pixel positions and values and checks them in the input image, flagging
    any errors. The output is numeric, and is the number of failing tests."""

    def __init__(self):
        super().__init__("pixtest", "testing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("results", Datum.TESTRESULT)

    def init(self, node):
        node.tests = []
        node.selected = None  # not persisted deliberately

    def serialise(self, node):
        return {'tests': [x.serialise() for x in node.tests]}

    def deserialise(self, node, d):
        node.tests = [PixTest.deserialise(x) for x in d['tests']]

    def createTab(self, xform, window):
        return TabPixTest(xform, window)

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        out = []
        node.failed = set()
        if img is not None:
            node.img = img.copy()
            node.img.setMapping(node.mapping)
            for i, t in enumerate(node.tests):
                # do the test
                if 0 <= t.x < img.w and 0 <= t.y < img.h:
                    if 0 <= t.band < img.channels:
                        val = img[t.x, t.y] if img.channels == 1 else img[t.x, t.y][t.band]
                        if not t.test(val):
                            out.append(f"test {i} failed: actual {val} != expected {t.val()}")
                            node.failed.add(i)
                    else:
                        out.append(f"band out of range in test {i}: {t.band}")
                        node.failed.add(i)
                else:
                    out.append(f"coords out of range in test{i}: {t.x}, {t.y}")
                    node.failed.add(i)

                node.img.annotations.append(IndexedPointAnnotation(
                    i, t.x, t.y, i == node.selected, QColor(t.col)))
                # ui.log("\n".join(out))
                if len(out) == 0:
                    node.setRectText("ALL OK")
                else:
                    node.setError(XFormException('TEST', f"{len(out)} FAILED"))
        else:
            node.img = None
            node.setError(XFormException('TEST', 'NO IMAGE'))
            out = ['NO IMAGE']

        node.graph.rebuildTabsAfterPerform = True
        node.out = Datum(Datum.TESTRESULT, out, sources=nullSourceSet)
        node.setOutput(0, node.out)

    def setFromPixels(self, node):
        """Forces all tests to pass by reading the image and setting the N, U and DQ values to the values
        stored in those pixels"""
        img = node.img
        for i, t in enumerate(node.tests):
            if 0 <= t.x < img.w and 0 <= t.y < img.h and 0 <= t.band < img.channels:
                val = img[t.x, t.y] if img.channels == 1 else img[t.x, t.y][t.band]
                # modify the test, converting to serializable types
                t.n = float(val.n)
                t.u = float(val.u)
                t.dq = int(val.dq)
            else:
                ui.log(f"cannot set test {i}, coords out of range")


class TabPixTest(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpixtest.ui')
        self.w.leftButton.clicked.connect(self.leftClicked)
        self.w.rightButton.clicked.connect(self.rightClicked)
        self.w.addButton.clicked.connect(self.addClicked)
        self.w.dupButton.clicked.connect(self.dupClicked)
        self.w.setFromPixelsButton.clicked.connect(self.setFromPixelsClicked)
        self.w.deleteButton.clicked.connect(self.deleteClicked)
        self.w.tableView.delete.connect(self.deleteClicked)
        self.w.tableView.selChanged.connect(self.selectionChanged)
        self.w.randButton.clicked.connect(self.randClicked)

        self.model = Model(self, node.tests)
        self.w.tableView.setModel(self.model)
        self.model.changed.connect(self.testsChanged)
        self.w.canvas.mouseHook = self
        self.w.tableView.setItemDelegateForRow(PixTest.getHeader().index('DQ'),
                                               DQDelegate(self.w.tableView, self.model))
        self.w.tableView.setItemDelegateForRow(PixTest.getHeader().index('col'),
                                               ComboBoxDelegate(self.w.tableView, self.model, COLOURS))

        self.nodeChanged()

    def selectionChanged(self, idx):
        self.node.selected = idx
        self.changed()

    def setFromPixelsClicked(self):
        if QMessageBox.question(self.parent(), "Set test from pixels",
                                "This will overwrite all test data to force the tests to pass. Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.node.img is None:
                ui.error("No image to read data from")
            else:
                self.mark()
                # yes, there are times when I wonder about the wisdom of the node/typesingleton model.
                self.node.type.setFromPixels(self.node)
                # and we need to tell the table about the test changes; the best(?) way to do this
                # is to just make a new model.
#                self.model = Model(self, self.node.tests)
#                self.w.tableView.setModel(self.model)
                self.changed()

    def leftClicked(self):
        """move left and then reselect the column we just moved"""
        if (col := self.w.tableView.get_selected_item()) is not None:
            self.model.move_left(col)
            self.w.tableView.selectItem(col - 1)

    def rightClicked(self):
        """move right and then reselect the column we just moved"""
        if (col := self.w.tableView.get_selected_item()) is not None:
            self.model.move_right(col)
            self.w.tableView.selectItem(col + 1)

    def addClicked(self):
        col = self.model.add_item()
        self.w.tableView.selectItem(col)

    def dupClicked(self):
        if (col := self.w.tableView.get_selected_item()) is not None:
            col = self.model.add_item(col)
            self.w.tableView.selectItem(col)

    def deleteClicked(self):
        if (col := self.w.tableView.get_selected_item()) is not None:
            if QMessageBox.question(self.window, "Delete test", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.model.delete_item(col)

    def randClicked(self):
        self.mark()
        self.model.add_random(self.node.img.channels, self.node.img.w, self.node.img.h)

    def testsChanged(self):
        """Tests have been changed in the UI, not programatically"""
        self.changed()

    def onNodeChanged(self):
        self.model.failed = self.node.failed
        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.img)

    def canvasMousePressEvent(self, x, y, e):
        if (item := self.w.tableView.get_selected_item()) is not None:
            self.mark()
            self.model.changePos(item, x, y)
            self.changed()

    def canvasMouseMoveEvent(self, x, y, e):
        pass

    def canvasMouseReleaseEvent(self, x, y, e):
        pass


def testFloat(inpval, test, testval):
    if test == 'Equals':
        return np.isclose(inpval, testval)
    elif test == 'Not equals':
        return not np.isclose(inpval, testval)
    elif test == 'Less than':
        return inpval < testval
    elif test == 'Greater than':
        return inpval > testval
    else:
        raise XFormException('INTR', f"bad comparison: {test}")


def testDQ(inpval, test, testval):
    if test == 'Equals':
        return inpval == testval
    if test == 'Does not equal':
        return inpval != testval
    if test == 'Contains':
        return (inpval & testval) > 0
    if test == 'Does not contain':
        return (inpval & testval) == 0
    else:
        raise XFormException('INTR', f"bad DQ comparison: {test}")


@xformtype
class XFormScalarTest(XFormType):
    """Test a scalar against a value"""

    def __init__(self):
        super().__init__("scalartest", "testing", "0.0.0")
        self.addInputConnector("", Datum.NUMBER)
        self.addOutputConnector("results", Datum.TESTRESULT)
        self.autoserialise = ('n', 'u', 'dq', 'nTest', 'uTest', 'dqTest')

    def init(self, node):
        node.n = 0
        node.u = 0
        node.dq = 0
        node.nTest = "Equals"
        node.uTest = "Equals"
        node.dqTest = "Equals"
        node.failed = set()

    def createTab(self, xform, window):
        return TabScalarTest(xform, window)

    def perform(self, node):
        v = node.getInput(0, Datum.NUMBER)
        out = None
        if v is not None:
            if not v.isscalar():
                out = f"Fail - input not scalar"
            elif not testFloat(v.n, node.nTest, node.n):
                out = f"Nominal fail: actual {v.n} {node.nTest} expected {node.n}"
            elif not testFloat(v.u, node.uTest, node.u):
                out = f"Uncertainty fail: actual {v.u} {node.uTest} expected {node.u}"
            elif not testDQ(v.dq, node.dqTest, node.dq):
                out = f"Uncertainty fail: actual {v.dq} {node.dqTest} expected {node.dq}"
        else:
            out = "NO VALUE"
        if out is None:
            out = []
        else:
            ui.log(out)
            out = [out]

        if len(out) == 0:
            node.setRectText("OK")
        else:
            node.setError(XFormException('TEST', f"{len(out)} FAILED"))

        node.graph.rebuildTabsAfterPerform = True
        node.out = Datum(Datum.TESTRESULT, out, nullSourceSet)
        node.setOutput(0, node.out)


class TabScalarTest(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabscalartest.ui')
        self.w.nCombo.currentTextChanged.connect(self.nComboChanged)
        self.w.uCombo.currentTextChanged.connect(self.uComboChanged)
        self.w.dqCombo.currentTextChanged.connect(self.dqComboChanged)

        self.w.nEdit.setValidator(QDoubleValidator(-math.inf, math.inf, -1, w))
        self.w.uEdit.setValidator(QDoubleValidator(0.0, 1000.0, -1, w))

        self.w.nEdit.textChanged.connect(self.nEditChanged)
        self.w.uEdit.textChanged.connect(self.uEditChanged)
        self.w.dqEditButton.clicked.connect(self.dqButtonClicked)
        self.w.setButton.clicked.connect(self.setButtonClicked)

        self.dontSetText = False
        self.dialog = None
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.nCombo.setCurrentText(self.node.nTest)
        self.w.uCombo.setCurrentText(self.node.uTest)
        self.w.dqCombo.setCurrentText(self.node.dqTest)
        self.w.dqEditButton.setText(dq.chars(self.node.dq, shownone=True))

        if not self.dontSetText:
            self.w.nEdit.setText(str(self.node.n))
            self.w.uEdit.setText(str(self.node.u))

    def nComboChanged(self, t):
        self.mark()
        self.node.nTest = t
        self.changed()

    def uComboChanged(self, t):
        self.mark()
        self.node.uTest = t
        self.changed()

    def dqComboChanged(self, t):
        self.mark()
        self.node.dqTest = t
        self.changed()

    def nEditChanged(self, t):
        v = 0 if t == '' else float(t)
        self.mark()
        self.node.n = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def uEditChanged(self, t):
        v = 0 if t == '' else float(t)
        self.mark()
        self.node.u = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def setButtonClicked(self):
        if (v := self.node.getInput(0, Datum.NUMBER)) is not None:
            self.mark()
            # make sure the types are serialisable
            self.node.n = float(v.n)
            self.node.u = float(v.u)
            self.node.dq = int(v.dq)
            self.changed()

    def dqButtonClicked(self):
        def done():
            self.mark()
            self.node.dq = self.dialog.get()
            self.changed()

        self.dialog = DQDialog(self.node.dq, self)
        self.dialog.accepted.connect(done)
        self.dialog.open()

    def dqEditChanged(self, t):
        v = 0 if t == '' else int(t)
        self.mark()
        self.node.dq = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False


@xformtype
class XFormMergeTests(XFormType):
    """Merge the results of many tests into a single list of failures. Test results are always lists of test
    failures, this simply concatenates those lists."""

    def __init__(self):
        super().__init__("mergetests", "testing", "0.0.0")
        for i in range(0, 8):
            self.addInputConnector("", Datum.TESTRESULT)
        self.addOutputConnector("results", Datum.TESTRESULT)
        self.params = TaggedDictType()  # no parameters

    def init(self, node):
        pass

    def createTab(self, xform, window):
        return TabData(xform, window)

    def perform(self, node):
        out = []
        testFound = False
        for i in range(0, 8):
            x = node.getInput(i, Datum.TESTRESULT)
            if x is not None:
                out += x
                testFound = True

        if not testFound:
            node.out = Datum(Datum.TESTRESULT, ["NO TESTS"], sources=nullSourceSet)
            node.setError(XFormException('TEST', f"{len(out)} FAILED"))
        else:
            node.out = Datum(Datum.TESTRESULT, out, sources=nullSourceSet)
            if len(out) == 0:
                node.setRectText("ALL OK")
            else:
                node.setError(XFormException('TEST', f"{len(out)} FAILED"))
        node.graph.rebuildTabsAfterPerform = True
        node.setOutput(0, node.out)


@xformtype
class XFormStringTest(XFormType):
    """Convert the output of a node into string. Assert that this matches a given string. Both
    strings are stripped of whitespace and CRLF is converted to LF."""

    def __init__(self):
        super().__init__("stringtest", "testing", "0.0.0")
        self.addInputConnector("", Datum.ANY)
        self.addOutputConnector("", Datum.TESTRESULT)
        self.autoserialise = ('string',)

    def init(self, node):
        node.string = ""
        node.inp = "No input yet"

    def createTab(self, xform, window):
        return TabStringTest(xform, window)

    def perform(self, node):
        out = None
        inp = node.getInput(0)
        if inp.val is not None:
            node.inp = str(inp.val).strip().replace('\r\n', '\n')
            if node.inp != node.string.strip():
                out = "Mismatch!"
        else:
            out = "NO INPUT"

        if out is None:
            node.setRectText("ALL OK")
            out = []
        else:
            node.setError(XFormException('TEST', out))
            ui.log(out)
            out = [out]

        node.graph.rebuildTabsAfterPerform = True
        node.out = Datum(Datum.TESTRESULT, out, nullSourceSet)
        node.setOutput(0, node.out)


class TabStringTest(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabstringtest.ui')
        self.w.finishedButton.clicked.connect(self.editFinished)
        self.w.expected.textChanged.connect(self.textChanged)
        self.nodeChanged()

    def textChanged(self):
        self.w.finishedButton.setStyleSheet("background-color:rgb(255,100,100)")

    def onNodeChanged(self):
        self.w.expected.setPlainText(self.node.params.string)
        self.w.finishedButton.setStyleSheet("")
        self.w.actual.setPlainText(self.node.inp)

    def editFinished(self, t):
        self.mark()
        self.node.params.string = self.w.expected.toPlainText()
        self.changed()


@xformtype
class XFormErrorTest(XFormType):
    """Check that a node produces an error. This node will run after all other nodes, but before its children.
    It checks that the string is the error code (e.g. 'DATA') """
    def __init__(self):
        super().__init__("errortest", "testing", "0.0.0")
        self.addInputConnector("", Datum.ANY)
        self.addOutputConnector("", Datum.TESTRESULT)
        self.params = TaggedDictType(
            string=("Error code to check for", str, "")
        )
        self.alwaysRunAfter = True

    def createTab(self, xform, window):
        return TabStringTest(xform, window)

    def perform(self, node):
        out = None
        if node.inputs[0] is not None:
            # Hacky. Get the NODE connected to the input.
            n, _ = node.inputs[0]
            if n.error is None:
                out = "NO ERROR"
            elif n.error.code != node.params.string.strip():
                out = f"{n.error.code}!={node.params.string.strip()}"
        else:
            out = "NO INPUT"

        if out is None:
            node.setRectText("ALL OK")
            out = []
        else:
            node.setError(XFormException('TEST', out))
            ui.log(out)
            out = [out]

        node.graph.rebuildTabsAfterPerform = True
        node.out = Datum(Datum.TESTRESULT, out, nullSourceSet)
        node.setOutput(0, node.out)
