import traceback

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot import ui
from pcot.expressions import ExpressionEvaluator
from pcot.xform import XFormType, xformtype, XFormException


@xformtype
class XFormExpr(XFormType):
    """
    Expression evaluator. The node box will show the text of the expression. The "run" button must be clicked to
    set the node to the new expression and perform it. Additionally, the output type must be set - the system cannot
    determine the output type from the input types.

    The four inputs are assigned to the variables a, b, c, and d. They are typically (but not necessarily) images
    or scalar values.

    Operators:
    *, -, /, +,^  operate on scalars, images and ROIs (see below for ROIs)
    -A            element-wise -A
    A.B           property B of entity A (e.g. a.h is height of image a)
    A$546         extract single channel image of wavelength 546
    A&B           element-wise minimum of A and B (Zadeh's AND operator)
    A|B           element-wise maximum of A and B (Zadeh's OR operator)
    !A            element-wise 1-A (Zadeh's NOT operator)

    ROI operators:
    a+b           union
    a*b           intersection
    a-b           difference
    Source ROIs from the "roi" output of ROI nodes. Impose resulting ROIs on images with "importroi" node.

    Properties are indicated by the "." operator, e.g. "a.w":
    h             height of an image
    w             width of an image
    n             pixel count of an image

    A list of functions can be obtained by right-clicking on either the log pane or function entry pane
    and selecting "List all functions." Help on an individual function can be found by hovering over
    the name of a function, right-clicking and selecting "Get help on 'somefunction'".

    """

    def __init__(self):
        super().__init__("expr", "maths", "0.0.0")
        self.parser = ExpressionEvaluator()
        self.addInputConnector("a", conntypes.ANY)
        self.addInputConnector("b", conntypes.ANY)
        self.addInputConnector("c", conntypes.ANY)
        self.addInputConnector("d", conntypes.ANY)
        self.addOutputConnector("", conntypes.VARIANT)
        self.autoserialise = ('expr',)

    def createTab(self, n, w):
        return TabExpr(n, w)

    def init(self, node):
        node.tmpexpr = ""
        node.expr = ""
        # used when we have an image on the output
        node.img = None
        # a string to display the image
        node.result = ""
        node.w = -1

    def perform(self, node):
        # we register the input vars here because we have to, they are temporary and apply to
        # this run only. To register other things, go to expression/eval.py.

        self.parser.registerVar('a', lambda: node.getInput(0))
        self.parser.registerVar('b', lambda: node.getInput(1))
        self.parser.registerVar('c', lambda: node.getInput(2))
        self.parser.registerVar('d', lambda: node.getInput(3))

        try:
            if len(node.expr.strip()) > 0:
                res = self.parser.run(node.expr)
                node.setOutput(0, res)
                if res is not None:
                    if res.tp == conntypes.IMG:
                        # if there's an image on the output, show it
                        node.img = res.val
                        node.img.setMapping(node.mapping)
                        node.result = "IMAGE"
                    elif res.tp == conntypes.NUMBER:
                        node.result = str(res.val)
                        node.setRectText("res: "+node.result)
                    else:
                        node.result = str(res.val)
                        node.setRectText("res: "+str(res.tp))

        except Exception as e:
            traceback.print_exc()
            node.result = str(e)
            raise XFormException('EXPR', str(e))


class TabExpr(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabexpr.ui')
        self.w.variant.setTitle("Output type")
        self.w.run.clicked.connect(self.run)
        self.w.expr.textChanged.connect(self.exprChanged)
        self.w.variant.changed.connect(self.variantChanged)
        self.w.expr.node = node   # need a link from the text edit box into the node, so we can get help on funcs.

        self.nodeChanged()

    def variantChanged(self, t):
        self.mark()
        self.node.outputTypes[0] = t
        self.node.graph.ensureConnectionsValid()
        self.changed()

    def exprChanged(self):
        self.node.tmpexpr = self.w.expr.toPlainText()
        self.node.displayName = self.node.expr.replace('\r', '').replace('\n', '').replace('\t', '')
        # don't call changed() or we'll run the expr on every key press!

    def run(self):
        self.mark()
        # note that we use a temporary expression, so that the expression isn't constantly changing and we have
        # difficulty marking undo points.
        self.node.expr = self.node.tmpexpr
        self.node.rect.setSizeToText(self.node)
        self.changed()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.variant.set(self.node.getOutputType(0))
        self.w.expr.setPlainText(self.node.expr)
        self.w.result.setPlainText(self.node.result)
        self.w.canvas.display(self.node.img)
