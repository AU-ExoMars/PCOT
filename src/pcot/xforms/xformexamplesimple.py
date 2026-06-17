"""
This is an example XFormType (node) class. This one uses the TabAggregate to edit the parameters, which
is an easy way of editing a node with simple TaggedDict parameters.
"""

from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import XFormType, xformtype, XForm, XFormException
from pcot.xforms.tabgeneric import TabGeneric


@xformtype
class XFormExampleSimpleParameters(XFormType):
    """
    This object is not a node, but the singleton to which nodes of this type point to
    determine their behaviour.

    This docstring will form the help text for the node in the UI. Markdown is permitted
    and processed into HTML. Look at (say) XFormColourMap for an example of how to write this.
    """

    def __init__(self):
        """
        Initialise the type singleton object. This doesn't create the *node*, but the single object that
        all nodes of this type will point to. This constructor runs at startup automatically (actually as part
        of importing PCOT).

        This example adds and multiplies, or multiplies and then adds, its input by
        a pair of constants.
        """

        # Call the superclass constructor with the name of the node type, the group it belongs to,
        # and the version number of the node type.
        # Because group is "hidden", we won't see it in the palette - it's just an example, not for actual use.

        # There are a couple of other parameters you can set here:
        # hasEnable=True - this will add a checkbox to the node's properties panel that allows the user to
        #                  disable the node temporarily. This is useful for nodes that are a bit slow.
        # startEnabled=False - this will start the node disabled. This is useful for nodes that are very slow.
        #                  It has no effect if hasEnable is false.

        super().__init__("simple", "testing", "0.0.0",
                         #  hasEnable=True,
                         #  startEnabled=False
                         )

        # set up parameters. This is a "tagged dictionary" - see the taggedaggregates.py file for more information,
        # but essentially it's a dict with description, type and default value for every item. This object
        # is the "type singleton" which defines the parameters for nodes of this type; calling create() on
        # it will create the actual TaggedDict instance. This is done automatically when we create a new node.
        #
        # We also have TaggedList, and both TaggedList and TaggedDict can contain other TaggedLists and TaggedDict.
        # Check out the tests in test_taggedaggs.py, some of those are quite complex.

        self.params = TaggedDictType(
            # this is a float parameter called "mul"" with a default value of 0.0. The UI will automatically
            # make an editor for it, as it will for all the parameters.
            mul=("multiply", float, 0.0),
            add=("add", float, 0.0),
            # this is a string parameter called "order" with a default value. It can have
            # several different specific values. If we didn't provide these it could have any value, and the
            # tab would have a text editor rather than a dropdown.
            order=("order of ops", str, "mul,add", ["mul,add","add,mul"])
        )

        # add input and output connectors. The first parameter is the name of the connector,
        # the second is the type of data that can be connected to it.
        # Connectors don't really need a name - they're displayed above the connector
        # in the UI if present.

        self.addInputConnector("", Datum.IMG)   # node input, an ImageCube datum
        self.addOutputConnector("", Datum.IMG)  # node output, an ImageCube datum

    def init(self, node: XForm):
        """
        This method is called to actually initialise a node (an XForm object). It typically does this by
        filling in some fields of the node object.
        Here, though, there's nothing to do because node.params will already have been created from self.params
        """
        pass

    def perform(self, node):
        """
        This runs automatically on a node whenever a node's input is changed,
        typically by nodes upstream of this one. It's where the node does its
        work.
        """
        params = node.params   # get a handy reference to the parameters TaggedDict

        # get the input image. This returns None if there is no input or the input is not an image.
        img: ImageCube = node.getInput(0, Datum.IMG)
        if img is not None:
            # there an image, let's do something with it. We're going to add a value to the pixels,
            # and multiply by another value. Or the other way around, depending on the ordering.
            # The values are stored in node.params under the keys given in the TaggedDictType above.

            # We first get a SubImageCube object from the image - this is the image clipped to
            # a bounding box around any ROIs in the image, with a mask for which pixels are in the ROIs.
            # We do this because we want the operation to be performed on the parts covered by
            # the ROIs.
            subimage = img.copy().subimage()  # make a copy (need to do this to avoid overwriting the source).

            # Now do the thing! We're operating on the img, uncertainty and dq fields inside the subimage.
            # I'm also doing uncertainty propagation - there are functions in value.py to handle that.

            from pcot.value import mul_unc, add_sub_unc

            if node.params.order == "mul,add":
                # do the multiplication of the nominal (mean) values first
                result_nom = subimage.img * node.params.mul
                # then handle the uncertainty - the parameters here are (mean1,unc1,mean2,unc2) for multiplication.
                # Note that the uncertainty for the constants is zero, which makes this trivial in reality.
                result_unc = mul_unc(subimage.img, subimage.uncertainty, params.mul, 0)
                result_nom = result_nom + node.params.add
                # for subtraction/addition, we don't need the nominals, just the uncertainties (which add in
                # quadrature). As you would expect, this operation isn't really needed because the uncertainty
                # is unchanged when you add a constant.
                result_unc = add_sub_unc(result_unc, 0)
            elif node.params.order == "add,mul":
                result_nom = subimage.img + node.params.add
                result_unc = add_sub_unc(subimage.uncertainty, 0)
                result_nom = result_nom * node.params.mul
                result_unc = mul_unc(result_nom, result_unc, params.mul, 0)
            else:
                # this is the kind of exception to raise when things go wrong in a node. The four-letter code
                # is shown in the node's graph box.
                raise XFormException('DATA', "Bad 'order' parameter")

            # The resulting DQ is going to be the same as the source image.
            result_dq = subimage.dq

            # splice the returned clipped image into the main image, producing a new image, and
            # make sure its RGB mapping is that specified in the node (this is handled by the canvas
            # control, which has been told by setNode to store its settings in the node).

            newimg = img.modifyWithSub(subimage, result_nom, uncertainty=result_unc, dqv=result_dq)
            newimg.setMapping(node.mapping)
        else:
            # if there's no input, just set the output image to None.
            newimg = None

        # wrap the output image in a Datum
        out = Datum(Datum.IMG, newimg)
        # and set the node's output to be that datum.
        node.setOutput(0, out)

    def createTab(self, node, window):
        """
        Create a tab for this node. This is a tab that will be displayed in the
        node's properties panel in the UI. It takes the node, which will be stored
        in the tab, and the window, which is the main window of the application.
        It just creates and returns a tab - in this case it's a "standard" tab for
        editing a node with simple parameters.

        If we want to display the data type and source info, add "source_section=True"
        """
        return TabGeneric(node, window)
