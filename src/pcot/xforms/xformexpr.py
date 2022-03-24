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
    
    The standard operators +,/,\*,- and ^ all have their usual meanings. When applied to images they work in
    a pixel-wise fashion, so if **a** is an image, **2\*a** will double the brightness. If **b** is also an image,
    **a+b** will add the two images, pixel by pixel. There are two non-standard operators: **.** for properties
    and **$** for band extraction. These are described below.


    ### Image/numeric operators:
    |operator    |description| precedence (higher binds tighter)
    |-------|-----------|----------------
    | + | add \[r\] | 10
    | - | subtract \[r\] | 10
    | / | divide \[r\] | 20
    | * | multiply \[r\] | 20
    | ^ | exponentiate \[r\] | 30
    |-A            |element-wise -A|50
    |A.B           |property B of entity A (e.g. a.h is height of image a)|80
    |A$546         |extract single channel image of wavelength 546|100
    |A&B           |element-wise minimum of A and B (Zadeh's AND operator)|20
    |A\|B          |element-wise maximum of A and B (Zadeh's OR operator)|20
    |!A            |element-wise 1-A (Zadeh's NOT operator)|50

    All operators can act on images and scalars (numeric values),
    with the exception of **.** and **$** which have images on the left-hand side and identifiers
    or integers on the right-hand side.
    Those operators marked with \[r\] can also act on pairs of ROIs (regions of interest, see below).
    
    ### Binary operations on image pairs
    These act by performing the binary operation on the two underlying Numpy arrays. This means you may need to be
    careful about the ordering of the bands in the two images, because they will simply be operated on in the order
    they appear.
    
    For example, consider adding two images $a$ and $b$ with the same bands in a slightly different order:

    | image *a* | image *b* | result of addition |
    |---------|----------|---------------|
    | 480nm | 480nm | sum of 480nm bands |
    | 500nm | 500nm | sum of 500nm bands |
    | 610nm | 670nm | *a*'s 610nm band plus *b*'s 670nm band ||
    | 670nm | 610nm | copy of previous band (addition being commutative) |
    
    This probably isn't what you wanted. Note that this is obviously not an issue when an operation is being performed
    on bands in a single image.

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

    ### Band extraction

    The notation **$name** or **$wavelength** takes an image on the left-hand
    side and extracts a single band, generating a new monochrome image. 
    The right-hand side is either a filter name, a filter position or a
    wavelength. Depending on the camera, all these could be valid: 

    | expression | meaning |
    |------------|---------|
    | **a$780**  | the 780nm band in image *a* |
    | **(a+b)$G0** | the band named G0 in the image formed by adding images *a* and *b* |
    | **((a+b)/2)$780** | the average of the 780nm bands of images *a* and *b* |
    
    Be aware of caveats in the "binary operations on image pairs" section above: it may be better to extract
    the band before performing the operation, thus:

    | old expression | better expression |
    |------------|---------|
    | **(a+b)$G0** | **a$G0 + b$G0** |
    | **((a+b)/2)$780** | **(a$780+b$780)/2**  |
    

    ### Properties

    Properties are indicated by the **.** operator, e.g. **a.w** to find an
    image's width.
    
    ### Help on functions and properties
    
    A list of functions can be obtained by right-clicking on either the log pane or function entry pane
    and selecting "List all functions." Help on an individual function can be found by hovering over
    the name of a function, right-clicking and selecting "Get help on 'somefunction'".
    Similar actions are supported for properties.


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
        self.node.rect.setSizeToText()
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
