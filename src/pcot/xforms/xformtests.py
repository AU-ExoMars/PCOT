import dataclasses
import math
from dataclasses import dataclass
from typing import List, Any

import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import QModelIndex, Signal, Qt
from PySide2.QtGui import QPainter, QPen, QColor, QIntValidator, QDoubleValidator
from PySide2.QtWidgets import QMessageBox

import pcot
from pcot import ui
from pcot.datum import Datum
from pcot.sources import nullSource, nullSourceSet
from pcot.ui.tablemodel import TableModel, ComboBoxDelegate
from pcot.utils import SignalBlocker
from pcot.value import Value
from pcot.xform import XFormType, xformtype, XFormException
from pcot.utils.annotations import Annotation, annotFont, IndexedPointAnnotation


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


class Model(TableModel):
    changed = Signal()

    def __init__(self, tab, _data: List[PixTest]):
        super().__init__(tab, PixTest, _data)

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview or any item delegates"""
        if index.isValid():
            self.tab.mark()  # we do the undo mark here, before the data is changed
            field = index.row()
            item = index.column()
            d = self.d[item]

            def convposint(v, prev):
                v = int(v)
                if v >= 0:
                    return v
                else:
                    return prev

            try:
                if field == 0:
                    d.x = convposint(value, d.x)
                elif field == 1:
                    d.y = convposint(value, d.y)
                elif field == 2:
                    d.band = convposint(value, d.band)
                elif field == 3:
                    d.n = float(value)
                elif field == 4:
                    d.u = float(value)
                elif field == 5:
                    d.dq = convposint(value, d.dq)
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

    def changePos(self, item, x, y):
        if 0 <= item < len(self.d):
            self.d[item].x = x
            self.d[item].y = y
            self.dataChanged.emit(QModelIndex(), QModelIndex(), (QtCore.Qt.DisplayRole,))
            self.changed.emit()


@xformtype
class XFormPixTest(XFormType):
    """Used in testing, but may be useful for running automated tests for users. Contains
    a table of pixel positions and values and checks them in the input image, flagging
    any errors. The output is numeric, and is the number of failing tests."""

    def __init__(self):
        super().__init__("pixtest", "utility", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("results", Datum.TESTRESULT)

    def init(self, node):
        node.tests = []

    def serialise(self, node):
        return {'tests': [x.serialise() for x in node.tests]}

    def deserialise(self, node, d):
        node.tests = [PixTest.deserialise(x) for x in d['tests']]

    def createTab(self, xform, window):
        return TabPixTest(xform, window)

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        out = []
        if img is not None:
            node.img = img.copy()
            for i, t in enumerate(node.tests):
                # do the test
                ok = False
                if 0 <= t.x < img.w and 0 <= t.y < img.h:
                    if 0 <= t.band < img.channels:
                        val = img[t.x, t.y] if img.channels == 1 else img[t.x, t.y][t.band]
                        if t.test(val):
                            ok = True
                        else:
                            out.append(f"test {i} failed: {val} != {t.val()}")
                    else:
                        out.append(f"band out of range in test {i}: {t.band}")
                else:
                    out.append(f"coords out of range in test{i}: {t.x}, {t.y}")
                node.img.annotations.append(IndexedPointAnnotation(
                    i, t.x, t.y, ok, QColor(t.col)))
                ui.log("\n".join(out))
                resultStr = "FAILED" if len(out) > 0 else "OK"
        else:
            node.img = None
            resultStr = "NOIMG"

        node.setRectText(resultStr)

        node.setOutput(0, Datum(Datum.TESTRESULT, out, sources=nullSourceSet))


class TabPixTest(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpixtest.ui')
        self.w.leftButton.clicked.connect(self.leftClicked)
        self.w.rightButton.clicked.connect(self.rightClicked)
        self.w.addButton.clicked.connect(self.addClicked)
        self.w.dupButton.clicked.connect(self.dupClicked)
        self.w.deleteButton.clicked.connect(self.deleteClicked)
        self.w.tableView.delete.connect(self.deleteClicked)

        self.model = Model(self, node.tests)
        self.w.tableView.setModel(self.model)
        self.model.changed.connect(self.testsChanged)
        self.w.canvas.mouseHook = self
        self.w.tableView.setItemDelegateForRow(PixTest.getHeader().index('col'),
                                               ComboBoxDelegate(self.model,
                                                                ['white', 'black', 'blue', 'green', 'red', 'yellow',
                                                                 'cyan', 'magenta', 'brown']))

        self.nodeChanged()

    def leftClicked(self):
        """move left and then reselect the column we just moved"""
        if (col := self.w.tableView.get_selected_item()) is not None:
            self.model.move_left(col)
            self.w.tableView.selectColumn(col - 1)

    def rightClicked(self):
        """move right and then reselect the column we just moved"""
        if (col := self.w.tableView.get_selected_item()) is not None:
            self.model.move_right(col)
            self.w.tableView.selectColumn(col + 1)

    def addClicked(self):
        col = self.model.add_item()
        self.w.tableView.selectColumn(col)

    def dupClicked(self):
        if (col := self.w.tableView.get_selected_item()) is not None:
            col = self.model.add_item(col)
            self.w.tableView.selectColumn(col)

    def deleteClicked(self):
        if (col := self.w.tableView.get_selected_item()) is not None:
            if QMessageBox.question(self.window, "Delete test", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.model.delete_item(col)

    def testsChanged(self):
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.display(self.node.img)

    def canvasMousePressEvent(self, x, y, e):
        if (col := self.w.tableView.get_selected_item()) is not None:
            self.mark()
            self.model.changePos(col, x, y)
            self.changed()

    def canvasMouseMoveEvent(self, x, y, e):
        pass

    def canvasMouseReleaseEvent(self, x, y, e):
        pass


def testFloat(inpval, test, testval):
    if test == 'Equals':
        return np.isclose(inpval,testval)
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
        super().__init__("scalartest", "utility", "0.0.0")
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

    def createTab(self, xform, window):
        return TabScalarTest(xform, window)

    def perform(self, node):
        v = node.getInput(0, Datum.NUMBER)
        out = None
        if v is not None:
            if not testFloat(v.n, node.nTest, node.n):
                out = f"Nominal fail: {v.n} {node.nTest} {node.n}"
            elif not testFloat(v.u, node.uTest, node.u):
                out = f"Uncertainty fail: {v.u} {node.uTest} {node.u}"
            elif not testDQ(v.dq, node.dqTest, node.dq):
                out = f"Uncertainty fail: {v.dq} {node.dqTest} {node.dq}"
            resultStr = "OK" if out is None else "FAILED"
        out = [] if out is None else [out]

        node.setOutput(0, Datum(Datum.TESTRESULT, out, nullSourceSet))
        node.setRectText(resultStr)


class TabScalarTest(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabscalartest.ui')
        self.w.nCombo.currentTextChanged.connect(self.nComboChanged)
        self.w.uCombo.currentTextChanged.connect(self.uComboChanged)
        self.w.dqCombo.currentTextChanged.connect(self.dqComboChanged)

        self.w.nEdit.setValidator(QDoubleValidator(float('-inf'), float('inf'), -1, w))
        self.w.uEdit.setValidator(QDoubleValidator(0.0, 1000.0, -1, w))
        self.w.dqEdit.setValidator(QIntValidator(0, 65535, w))

        self.w.nEdit.textChanged.connect(self.nEditChanged)
        self.w.uEdit.textChanged.connect(self.uEditChanged)
        self.w.dqEdit.textChanged.connect(self.dqEditChanged)

        self.dontSetText = False
        self.nodeChanged()

    def onNodeChanged(self):
        self.w.nCombo.setCurrentText(self.node.nTest)
        self.w.uCombo.setCurrentText(self.node.uTest)
        self.w.dqCombo.setCurrentText(self.node.dqTest)

        if not self.dontSetText:
            self.w.nEdit.setText(str(self.node.n))
            self.w.nEdit.setText(str(self.node.u))
            self.w.nEdit.setText(str(self.node.dq))

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
        self.node.n = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def dqEditChanged(self, t):
        v = 0 if t == '' else int(t)
        self.mark()
        self.node.n = v
        self.dontSetText = True
        self.changed()
        self.dontSetText = False
