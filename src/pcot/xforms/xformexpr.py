import traceback
import logging

from pcot import ui
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.expressions import ExpressionEvaluator
from pcot.imagecube import ChannelMapping
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XFormException, XForm

logger = logging.getLogger(__name__)


def getvar(d):
    """check that a variable is not ANY (unwired). Also, if it's an image, make a shallow copy (see Issue #56, #65)"""
    if d.tp == Datum.ANY:
        raise XFormException("DATA", "variable's input is not connected")
    elif d.tp == Datum.IMG:
        if d.val is not None:
            d = Datum(Datum.IMG, d.val.shallowCopy())
    return d


@xformtype
class XFormExpr(XFormType):
    r"""
    Expression evaluator. The node box will show the text of the expression. The "run" button must be clicked to
    set the node to the new expression and perform it. The input can accept any type of data
    and the output type is determined when the node is run.

    The four inputs are assigned to the variables a, b, c, and d. They are typically (but not necessarily) images
    or numeric values.
    
    The standard operators +,/,\*,- and ^ all have their usual meanings. When applied to images they work in
    a pixel-wise fashion, so if **a** is an image, **2\*a** will double the brightness. If **b** is also an image,
    **a+b** will add the two images, pixel by pixel. There are two non-standard operators: **.** for properties
    and **$** for band extraction. These are described below.


    ### Image/numeric operators:
    |operator    |description| precedence (higher binds tighter)
    |-------|-----------|----------------
    |A + B| add A to B (can act on ROIs)| 10
    |A - B| subtract A from B (can act on ROIs)| 10
    |A / B| divide A by B (can act on ROIs)| 20
    |A * B| multiply A by B (can act on ROIs)| 20
    |A ^ B| exponentiate A to the power B (can act on ROIs)| 30
    |-A            |element-wise negation of A (can act on ROIs)|50
    |A.B           |property B of entity A (e.g. a.h is height of image a)|80
    |A$546         |extract single band image of wavelength 546|100
    |A$_2          |extract single band image from band 2 explicitly|100
    |A&B           |element-wise minimum of A and B (Zadeh's AND operator)|20
    |A\|B          |element-wise maximum of A and B (Zadeh's OR operator)|20
    |!A            |element-wise 1-A (Zadeh's NOT operator)|50

    All operators can act on images, 1D vectors and scalars
    with the exception of **.** and **$** which have images on the left-hand side and identifiers
    or integers on the right-hand side.

    Those operators marked with **(can act on ROIs)** can also act on pairs of ROIs (regions of interest, see below).
    
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

    ### Binary operators on images with regions of interest
    If one of the two images has an ROI, the operation is only performed on that ROI; the remaining area of output is
    taken from the image without an ROI. If both images have an ROI an error will result - it is likely that this
    is a mistake on the user's part, and doing something more "intelligent" might conceal this. The desired result
    can be achieved using expr nodes on ROIs and an importroi node.

    ### Operations with vectors
    Some functions can generate vectors, such as `mean` for getting the means of the bands, and `vec` for generating
    vectors by hand.
    
    If an image is used in a binary operation with a vector on the other side, the vector must have the same number of
    elements as there are bands in the image. The operation will be performed on each band. Consider a 3-band image
    and the vector `[2,3,4]`. If we multiply them, the result will an image with the first band multiplied by 2,
    the second band multiplied by 3, and the third band multiplied by 4. 
    
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

    The right-hand side is either a filter name, a filter position, a
    wavelength or a band index preceded by "_". Depending on the camera, all these could be valid:

    | expression | meaning |
    |------------|---------|
    | **a$780**  | the 780nm band in image *a* |
    | **a$_2**  | band 2 in the image *a* |
    | **(a+b)$G0** | the band named G0 in the image formed by adding images *a* and *b* |
    | **((a+b)/2)$780** | the average of the 780nm bands of images *a* and *b* |
    
    Be aware of caveats in the "binary operations on image pairs" section above: it may be better to extract
    the band before performing the operation, thus:

    | old expression | better expression |
    |------------|---------|
    | **(a+b)$G0** | **a$G0 + b$G0** |
    | **((a+b)/2)$780** | **(a$780+b$780)/2**  |

    ### Brackets

    Round brackets are used to group expressions as usual, but square brackets are used for indexing into a vector.
    For example, **a[3]** will extract the fourth element of the vector **a**. However, square brackets cannot
    (yet) create a vector. To do this, use the `vec` function - so `vec(1,2,3)[1]` will return 2.
    
    Band extraction can also be performed with vectors provided the vector elements are numeric (i.e. wavelengths):
    `a $ vec(640,550,440)` is valid.
    

    ### Properties

    Properties are indicated by the **.** operator, e.g. **a.w** to find an
    image's width.
    
    ### Help on functions and properties
    
    A list of functions can be obtained by right-clicking on either the log pane or function entry pane
    and selecting "List all functions." Help on an individual function can be found by hovering over
    the name of a function, right-clicking and selecting "Get help on 'somefunction'".
    Similar actions are supported for properties.

    ## Uncertainties are assumed to be independent in all binary operations

    While uncertainty is propagated through operations (as population standard deviation) all quantities are assumed
    to be independent (calculating covariances is beyond the scope of this system). Be very careful here.
    For example, the uncertainty for the expression **tan(a)** will be calculated correctly, but if you try
    to use **sin(a)/cos(a)** the uncertainty will be incorrect because the nominator and denominator are
    not independent.


    """

    def __init__(self):
        super().__init__("expr", "maths", "0.0.0")
        self.parser = ExpressionEvaluator()

        self.addInputConnector("a", Datum.ANY)
        self.addInputConnector("b", Datum.ANY)
        self.addInputConnector("c", Datum.ANY)
        self.addInputConnector("d", Datum.ANY)
        self.addOutputConnector("", Datum.NONE)   # this changes type dynamically
        self.params = TaggedDictType(
            expr=("Expression to evaluate", str, "")
        )

    def createTab(self, n, w):
        return TabExpr(n, w)

    def init(self, node):
        # used when we have an image on the output. We keep this unlike a lot of other nodes so
        # we can see when the channel count changes.
        node.img = None
        # a string to display the image
        node.resultStr = ""
        node.w = -1

    def getDisplayName(self, n):
        """Custom text - if displayName is not the same as the type name, use that. Otherwise use
        the expression."""
        if n.displayName != "expr":
            # the user has changed the name, so use that
            return n.displayName
        else:
            # The node still has the default display name "expr".
            # get the expression and build a string for it, but say NONE if the expression isn't set yet
            e = n.params.expr
            return "NONE" if e == '' else e.replace('\r', '').replace('\n', '').replace('\t', '')

    def perform(self, node: XForm):
        # we register the input vars here because we have to, they are temporary and apply to
        # this run only. To register other things, go to expression/eval.py.

        self.parser.registerVar('a', 'value of input a', lambda: getvar(node.getInput(0)))
        self.parser.registerVar('b', 'value of input b', lambda: getvar(node.getInput(1)))
        self.parser.registerVar('c', 'value of input c', lambda: getvar(node.getInput(2)))
        self.parser.registerVar('d', 'value of input d', lambda: getvar(node.getInput(3)))

        try:
            expr = node.params.expr.strip()
            if len(expr) > 0:
                # get the previous number of channels (or None if the result is not an image)
                oldChans = None if node.img is None else node.img.channels
                # run the expression
                res = self.parser.run(expr)
                node.setOutput(0, res)
                if res is not None:   # should never be None, but I'll leave this in
                    node.img = None
                    node.changeOutputType(0, res.tp)   # change the output type
                    if res.tp.image:
                        # if there's an image on the output, show it
                        node.img = res.val
                        if node.img is not None:
                            # if the number of channels has changed, reset the mapping
                            if oldChans is not None and node.img.channels != oldChans:
                                node.mapping = ChannelMapping()
                            node.img.setMapping(node.mapping)
                    node.resultStr = res.tp.getDisplayString(res)
                    node.setRectText(res.tp.getDisplayString(res, True))
                else:
                    # no output, so reset the output type
                    node.changeOutputType(0, Datum.NONE)

        except Exception as e:
            traceback.print_exc()
            node.img = None
            node.setOutput(0, Datum.null)
            node.changeOutputType(0, Datum.NONE)
            node.resultStr = str(e)
            ui.error(f"Error in expression: {str(e)}")
            raise XFormException('EXPR', str(e))


class TabExpr(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabexpr.ui')
        self.w.run.clicked.connect(self.run)
        self.w.expr.textChanged.connect(self.exprChanged)
        self.w.expr.node = node   # need a link from the text edit box into the node, so we can get help on funcs.

        self.nodeChanged()

    def exprChanged(self):
        # set a red background to show the user that they have to click run
        self.w.run.setStyleSheet("background-color:rgb(255,100,100)")
        # we don't call changed() or we'll run the expr on every key press!

    def run(self):
        self.mark()
        self.node.params.expr = self.w.expr.toPlainText()
        self.node.rect.setSizeToText()
        # clear the RUN button's red background
        self.w.run.setStyleSheet("")
        self.changed()

    def onNodeChanged(self):
        self.w.data.canvas.setNode(self.node)
        with SignalBlocker(self.w.expr):
            self.w.expr.setPlainText(self.node.params.expr)
        d = self.node.getOutputDatum(0)
        self.w.data.display(d)
