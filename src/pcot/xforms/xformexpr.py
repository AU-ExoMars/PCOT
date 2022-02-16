import traceback

from pcot import ui
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.expressions import ExpressionEvaluator
from pcot.imagecube import ChannelMapping
from pcot.xform import XFormType, xformtype, XFormException


@xformtype
class XFormExpr(XFormType):
    """
    Expression evaluator. The node box will show the text of the expression. The "run" button must be clicked to
    set the node to the new expression and perform it. Additionally, the output type must be set - the system cannot
    determine the output type from the input types.

    The four inputs are assigned to the variables a, b, c, and d. They are typically (but not necessarily) images
    or scalar values.

    ### Image/numeric operators:
    |operator    |description|
    |-------|-----------|
    |*, -, /, +,^  |operate on scalars, images and ROIs (see below for ROIs)|
    |-A            |element-wise -A|
    |A.B           |property B of entity A (e.g. a.h is height of image a)|
    |A$546         |extract single channel image of wavelength 546|
    |A&B           |element-wise minimum of A and B (Zadeh's AND operator)|
    |A\|B          |element-wise maximum of A and B (Zadeh's OR operator)|
    |!A            |element-wise 1-A (Zadeh's NOT operator)|

    ### ROIs on images in binary operators
    If one of the two images has an ROI, the operation is only performed on that ROI; the remaining image is
    the left-hand side of the operation passed through unchanged. If both images have an ROI, the ROIs must have
    identical bounding boxes (see ops.py:twoImageBinop() ).



    ### Operators on ROIs themselves (as opposed to images with ROIs)
    |operator    |description|
    |----------|--------------|
    |a+b |          union|
    |a*b  |         intersection|
    |a-b |          difference|

    You can source ROIs from the "roi" output of ROI nodes, and impose resulting ROIs on images with "importroi" node.

    ### Properties

    Properties are indicated by the "." operator, e.g. "a.w":
    
    |Property |  description|
    |------|-----------|
    |h  |           height of an image|
    |w   |          width of an image|
    |n    |         pixel count of an image|

    A list of functions can be obtained by right-clicking on either the log pane or function entry pane
    and selecting "List all functions." Help on an individual function can be found by hovering over
    the name of a function, right-clicking and selecting "Get help on 'somefunction'".

    """

    def __init__(self):
        super().__init__("expr", "maths", "0.0.0")
        self.parser = ExpressionEvaluator()
        self.addInputConnector("a", Datum.ANY)
        self.addInputConnector("b", Datum.ANY)
        self.addInputConnector("c", Datum.ANY)
        self.addInputConnector("d", Datum.ANY)
        self.addOutputConnector("", Datum.VARIANT)
        self.autoserialise = ('expr',)

    def createTab(self, n, w):
        return TabExpr(n, w)

    def init(self, node):
        node.tmpexpr = ""
        node.expr = ""
        # used when we have an image on the output
        node.img = None
        # a string to display the image
        node.resultStr = ""
        node.w = -1

    def perform(self, node):
        # we register the input vars here because we have to, they are temporary and apply to
        # this run only. To register other things, go to expression/eval.py.

        self.parser.registerVar('a', 'value of input a', lambda: node.getInput(0))
        self.parser.registerVar('b', 'value of input b', lambda: node.getInput(1))
        self.parser.registerVar('c', 'value of input c', lambda: node.getInput(2))
        self.parser.registerVar('d', 'value of input d', lambda: node.getInput(3))

        try:
            if len(node.expr.strip()) > 0:
                # get the previous number of channels (or None if the result is not an image)
                oldChans = None if node.img is None else node.img.channels
                # run the expression
                res = self.parser.run(node.expr)
                print(res)
                node.setOutput(0, res)
                if res is not None:
                    node.img = None
                    if res.tp == Datum.IMG:
                        # if there's an image on the output, show it
                        node.img = res.val
                        # if the number of channels has changed, reset the mapping
                        if oldChans is not None and node.img.channels != oldChans:
                            node.mapping = ChannelMapping()
                        node.img.setMapping(node.mapping)
                        node.resultStr = "IMAGE"
                    elif res.tp == Datum.NUMBER:
                        node.resultStr = str(res.val)
                        node.setRectText("res: "+node.resultStr)
                    else:
                        node.resultStr = str(res.val)
                        node.setRectText("res: "+str(res.tp))

        except Exception as e:
            traceback.print_exc()
            node.resultStr = str(e)
            ui.error(f"Error in expression: {str(e)}")
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
        self.w.result.setPlainText(self.node.resultStr)
        self.w.canvas.display(self.node.img)
